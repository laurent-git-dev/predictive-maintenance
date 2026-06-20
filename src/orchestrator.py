"""Medallion orchestrator: run every source through Bronze then Silver layers.

For each source declared in ``src/sources/registry.py``:
1. **Bronze** : raw data (operators pseudonymised) → per-feature understanding +
   reports + load into the ``bronze`` schema.
2. **Silver** : treated data (feature engineering, encoding, imputation, outliers)
   → same per-feature reports + load into the ``silver`` schema.

Then the cross-source analysis is run. One command, idempotent (tables reloaded).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from src import config
from src.analyses.runner import run_default as run_cross_source
from src.common.env import load_dotenv
from src.common.registry import upsert_run
from src.common.stage import run_layer
from src.database import engine as db_engine
from src.sources.registry import SOURCE_SPECS, SourceSpec

logger = logging.getLogger(__name__)


def _artifacts_base(source: str) -> Path:
    dirname = config.source_artifacts_dirname(source)
    return config.PROJECT_ROOT / "artifacts" / "ingestions" / dirname


def run_source(spec: SourceSpec, engine=None) -> dict:
    """Run one source through the Bronze and Silver layers."""
    logger.info("=== Source: %s ===", spec.name)
    run_id = datetime.now().strftime("%Y%m%d%H%M")
    base = _artifacts_base(spec.name)
    run_dir = base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    bronze_df = spec.load_bronze()
    bronze = run_layer(
        bronze_df,
        source=spec.name,
        layer="bronze",
        run_dir=run_dir,
        numeric_features=spec.bronze_numeric,
        machine_col=spec.machine_col,
        table=spec.table,
        schema=config.BRONZE_SCHEMA,
        count_features=spec.count_features,
        count_label=spec.count_label,
        keyword_bars=spec.keyword_bars,
        heatmaps=spec.heatmaps,
        timeseries=spec.timeseries,
        bars_by_machine=spec.bars_by_machine,
        cumulative=spec.cumulative,
        feature_plots=spec.feature_plots,
        engine=engine,
    )

    if spec.bronze_only:
        # Bronze-only source (e.g. the machine dimension): no standalone Silver table.
        upsert_run(
            base / "runs_registry.json",
            {
                "run_id": run_id,
                "folder": run_dir.relative_to(config.PROJECT_ROOT).as_posix(),
                "bronze_rows": bronze["rows"],
                "silver_rows": None,
                "bronze_db": bronze["db"],
                "silver_db": "n/a (bronze-only source)",
            },
        )
        return {"run_dir": str(run_dir), "bronze": bronze, "silver": None}

    silver_df, report = spec.to_silver(bronze_df)
    silver = run_layer(
        silver_df,
        source=spec.name,
        layer="silver",
        run_dir=run_dir,
        numeric_features=spec.silver_numeric,
        machine_col=spec.machine_col,
        table=spec.table,
        schema=config.SILVER_SCHEMA,
        count_features=spec.count_features,
        count_label=spec.count_label,
        keyword_bars=spec.keyword_bars,
        heatmaps=spec.heatmaps,
        timeseries=spec.timeseries,
        bars_by_machine=spec.bars_by_machine,
        cumulative=spec.cumulative,
        feature_plots=spec.feature_plots,
        encodings=report.get("encode"),
        engine=engine,
    )

    upsert_run(
        base / "runs_registry.json",
        {
            "run_id": run_id,
            "folder": run_dir.relative_to(config.PROJECT_ROOT).as_posix(),
            "bronze_rows": bronze["rows"],
            "silver_rows": silver["rows"],
            "bronze_db": bronze["db"],
            "silver_db": silver["db"],
        },
    )
    return {"run_dir": str(run_dir), "bronze": bronze, "silver": silver}


def _get_engine(load_db: bool):
    if load_db and db_engine.is_available():
        return db_engine.get_engine()
    if load_db:
        logger.warning("PostgreSQL unavailable — database load SKIPPED.")
    return None


def run_source_by_name(name: str, load_db: bool = True) -> dict:
    """Run a single source (by name) through the layers — used by per-source CLIs."""
    load_dotenv(config.PROJECT_ROOT / ".env")
    spec = next(s for s in SOURCE_SPECS if s.name == name)
    return run_source(spec, _get_engine(load_db))


def run_pipeline(load_db: bool = True) -> dict:
    """Run all sources (Bronze + Silver) then the cross-source analysis."""
    load_dotenv(config.PROJECT_ROOT / ".env")
    engine = _get_engine(load_db)

    results: dict = {}
    for spec in SOURCE_SPECS:
        results[spec.name] = run_source(spec, engine)

    logger.info("=== Cross-source analysis ===")
    results["cross_source"] = {"run_dir": str(run_cross_source())}

    logger.info("Pipeline finished: %s", ", ".join(results))
    return results
