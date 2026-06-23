"""Medallion orchestrator: run every source through Bronze and Silver, then build Gold.

For each source declared in ``src/sources/registry.py``:
1. **Bronze** : raw data (operators pseudonymised) → per-feature understanding +
   reports + load into the ``bronze`` schema.
2. **Silver** : treated data (dedup, dimension merge, encoding, imputation,
   interpolation, normalization) → same reports + load into the ``silver`` schema.

Then a **single Gold table** (``gold.features``, one row per ``(machine_id, hour)``) is
built from the three Silver frames (``src/gold/features.py``) and a cross-source analysis
is run. One command, idempotent (tables reloaded).
"""

from __future__ import annotations

import logging
from pathlib import Path

from src import config
from src.framework.common.env import load_dotenv
from src.framework.common.registry import upsert_run
from src.framework.common.stage import run_layer
from src.framework.db import engine as db_engine
from src.framework.lineage.quality import check_quality
from src.framework.lineage.tracker import Batch
from src.settings import require_salt
from src.usecase.analyses.runner import run_default as run_cross_source
from src.usecase.gold.features import (
    FEATURES_COUNT,
    FEATURES_NUMERIC,
    build_gold_features,
    build_gold_from_db,
)
from src.usecase.ingestion.load import ingest_bronze
from src.usecase.silver.refine import refine_silver
from src.usecase.sources.registry import SOURCE_SPECS, SourceSpec, gold_sources

logger = logging.getLogger(__name__)


def _artifacts_base(source: str) -> Path:
    dirname = config.source_artifacts_dirname(source)
    return config.PROJECT_ROOT / "artifacts" / "ingestions" / dirname


def run_source(spec: SourceSpec, engine=None, batch: Batch | None = None) -> dict:
    """Run one source through the Bronze and Silver layers (returns its Silver frame)."""
    batch = batch or Batch(engine)
    logger.info("=== Source: %s ===", spec.name)
    run_id = batch.batch_id  # one identifier per run: artifacts ↔ meta.processing_runs
    base = _artifacts_base(spec.name)
    run_dir = base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    bronze_df = spec.load_bronze()
    # Bronze profiling + reports + CSV (no generic DB write); the DB load goes through the
    # validating ingestion (Pydantic flags + SQLAlchemy/Alembic-managed bronze.* tables).
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
        engine=None,
    )
    if engine is not None:
        out_ref = f"{config.BRONZE_SCHEMA}.{spec.table}"
        with batch.step(
            "ingest",
            layer="bronze",
            # Disambiguate the two machines.sql sources: machines_machine / machines_maintenance.
            source=config.source_artifacts_dirname(spec.name),
            input_ref=f"datalake/{spec.raw_ref or spec.name}",
            output_ref=out_ref,
        ) as st:
            flagged, ingest_status = ingest_bronze(spec.name, bronze_df, engine)
            qok, qdet = check_quality(out_ref, flagged, engine, batch.batch_id)
            qdet["parse_ko"] = ingest_status["parse_ko"]
            st.set(
                rows_read=len(bronze_df),
                rows_ingested=ingest_status["rows"],
                rows_rejected=0,
                quality_ok=qok,
                details=qdet,
                output_df=flagged,
            )
        bronze["db"] = ingest_status["db"]

    if spec.bronze_only:
        # Bronze-only source (e.g. the machine dimension): no standalone Silver table.
        upsert_run(
            base / "runs_registry.json",
            {
                "run_id": run_id,
                "code_version": batch.code_version,
                "folder": run_dir.relative_to(config.PROJECT_ROOT).as_posix(),
                "bronze_rows": bronze["rows"],
                "silver_rows": None,
                "bronze_db": bronze["db"],
                "silver_db": "n/a (bronze-only source)",
            },
        )
        return {"run_dir": str(run_dir), "bronze": bronze, "silver": None, "silver_df": None}

    # Silver starts from the ingested bronze.* tables (reject/correct + treatments). When the
    # DB is unavailable, fall back to the in-memory raw bronze so the pipeline still runs.
    if engine is not None:
        in_ref, out_ref = (
            f"{config.BRONZE_SCHEMA}.{spec.table}",
            f"{config.SILVER_SCHEMA}.{spec.table}",
        )
        with batch.step(
            # Silver merges the dimension into the maintenance facts -> label by the Silver table.
            "refine",
            layer="silver",
            source=spec.table,
            input_ref=in_ref,
            output_ref=out_ref,
        ) as st:
            silver_df, report, sstats = refine_silver(spec.name, engine)
            qok, qdet = check_quality(out_ref, silver_df, engine, batch.batch_id)
            qdet.update(sstats["modifications"])
            st.set(
                rows_read=sstats["bronze_rows"],
                rows_ingested=sstats["silver_rows"],
                rows_rejected=sstats["rejected"],
                quality_ok=qok,
                details=qdet,
                output_df=silver_df,
            )
    else:
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
            "code_version": batch.code_version,
            "folder": run_dir.relative_to(config.PROJECT_ROOT).as_posix(),
            "bronze_rows": bronze["rows"],
            "silver_rows": silver["rows"],
            "bronze_db": bronze["db"],
            "silver_db": silver["db"],
        },
    )
    return {"run_dir": str(run_dir), "bronze": bronze, "silver": silver, "silver_df": silver_df}


def run_gold(silver_by_source: dict, engine=None, batch: Batch | None = None) -> dict:
    """Build the single Gold feature table from the Silver frames and load it.

    ``silver_by_source`` maps ``incidents`` / ``telemetry`` / ``maintenance`` to their
    Silver DataFrame (the maintenance frame comes from the ``machines`` source).
    """
    batch = batch or Batch(engine)
    logger.info("=== Gold: unified feature table (machine x hour) ===")
    run_id = batch.batch_id  # same identifier as the sources / meta.processing_runs
    run_dir = config.GOLD_ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Gold starts from the silver.* DB tables; fall back to in-memory frames if no DB.
    out_ref = f"{config.GOLD_SCHEMA}.{config.GOLD_TABLE}"
    with batch.step(
        "build",
        layer="gold",
        source="gold",
        input_ref=f"{config.SILVER_SCHEMA}.*",
        output_ref=out_ref,
    ) as st:
        gold_df = (
            build_gold_from_db(engine)
            if engine is not None
            else build_gold_features(silver_by_source)
        )
        qok, qdet = check_quality(
            out_ref, gold_df, engine, batch.batch_id, grain=[config.MACHINE_COLUMN, "window_start"]
        )
        st.set(
            rows_read=len(gold_df),
            rows_ingested=len(gold_df),
            rows_rejected=0,
            quality_ok=qok,
            details=qdet,
            output_df=gold_df,
        )
    gold = run_layer(
        gold_df,
        source="gold",
        layer="gold",
        run_dir=run_dir,
        numeric_features=FEATURES_NUMERIC,
        machine_col=config.MACHINE_COLUMN,
        table=config.GOLD_TABLE,
        schema=config.GOLD_SCHEMA,
        count_features=FEATURES_COUNT,
        count_label="machine-hours",
        engine=engine,
        nest_layer=False,  # Gold is a single layer: artifacts live directly under the run dir
    )
    upsert_run(
        config.GOLD_RUNS_REGISTRY_PATH,
        {
            "run_id": run_id,
            "code_version": batch.code_version,
            "folder": run_dir.relative_to(config.PROJECT_ROOT).as_posix(),
            "gold_rows": gold["rows"],
            "gold_db": gold["db"],
        },
    )
    return {"run_dir": str(run_dir), "gold": gold}


def _get_engine(load_db: bool):
    if load_db and db_engine.is_available():
        return db_engine.get_engine()
    if load_db:
        logger.warning("PostgreSQL unavailable — database load SKIPPED.")
    return None


def run_source_by_name(name: str, load_db: bool = True) -> dict:
    """Run a single source (by name) through the layers — used by per-source CLIs."""
    load_dotenv(config.PROJECT_ROOT / ".env")
    require_salt()  # fail fast: operator PII pseudonymisation needs a configured salt
    spec = next(s for s in SOURCE_SPECS if s.name == name)
    return run_source(spec, _get_engine(load_db))


def run_pipeline(load_db: bool = True) -> dict:
    """Run all sources (Bronze + Silver), build the unified Gold table, then cross-source."""
    load_dotenv(config.PROJECT_ROOT / ".env")
    require_salt()  # fail fast: operator PII pseudonymisation needs a configured salt
    engine = _get_engine(load_db)
    batch = Batch(engine)  # one batch_id for the whole pipeline run (lineage raw -> gold)
    logger.info("=== Batch %s (code %s) ===", batch.batch_id, batch.code_version)

    results: dict = {}
    for spec in SOURCE_SPECS:
        results[spec.name] = run_source(spec, engine, batch)

    # Single Gold table from the Silver frames; each Gold slot maps to its source via the
    # registry (``gold_role``), e.g. maintenance <- the `machines` source.
    silver_by_source = {
        role: results[spec.name]["silver_df"] for role, spec in gold_sources().items()
    }
    results["gold"] = run_gold(silver_by_source, engine, batch)

    logger.info("=== Cross-source analysis ===")
    results["cross_source"] = {"run_dir": str(run_cross_source())}

    logger.info("Pipeline finished: %s", ", ".join(results))
    return results
