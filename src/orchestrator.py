"""Pipeline orchestrator: run every source through all stages.

For each source declared in ``src/sources/registry.py``:
1. **ingestion + understanding** (existing per-source runner → artifacts + reports),
2. **processing** (transformation / imputation / outliers → ``processed.csv``),
3. **loading** into PostgreSQL (skipped with a warning if the DB is unavailable).

Then the cross-source analysis is run. Re-running the whole thing is a single
command and is idempotent (DB tables are fully reloaded).
"""

from __future__ import annotations

import logging
from pathlib import Path

from src import config
from src.analyses.runner import run_default as run_cross_source
from src.common.env import load_dotenv
from src.database import engine as db_engine
from src.database.loader import write_table
from src.processing.pipeline import apply_processing
from src.sources.registry import SOURCE_SPECS, SourceSpec

logger = logging.getLogger(__name__)


def _write_processing_report(run_dir: Path, spec: SourceSpec, report: dict, db_status: str) -> None:
    """Write a short markdown summary of the processing + DB-load stages."""
    lines = [f"# Processing & loading — {spec.name}", ""]
    enc = report.get("encode", {})
    imp = report.get("impute", {})
    out = report.get("outliers", {})
    lines.append("## Transformation (text → value)")
    lines += [f"- `{c}` → `{n}`" for c, n in enc.items()] or ["- _(none)_"]
    lines.append("\n## Imputation")
    lines += [f"- `{c}`: {d['strategy']} ({d['n_filled']} filled)" for c, d in imp.items()] or [
        "- _(none)_"
    ]
    lines.append("\n## Outliers (IQR clip)")
    lines += [
        f"- `{c}`: {d['n_clipped']} clipped to [{d['low']}, {d['high']}]" for c, d in out.items()
    ] or ["- _(none)_"]
    lines.append(f"\n## Database load\n\n- {db_status}")
    (run_dir / "processing_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_source(spec: SourceSpec, engine=None) -> dict:
    """Run one source through ingestion+understanding, processing and DB load."""
    logger.info("=== Source: %s ===", spec.name)
    run_dir = Path(spec.run_understanding())  # stage 1+2 (existing runner)

    df = spec.load_dataframe()  # DB-ready base (anonymised for PII sources)
    processed, report = apply_processing(df, spec.processing)  # stage 3

    csv_path = run_dir / "processed.csv"
    processed.to_csv(csv_path, index=False, encoding=config.CSV_ENCODING)
    logger.info(
        "Processed dataset: %s (%d rows, %d columns)",
        csv_path.name,
        len(processed),
        processed.shape[1],
    )

    if engine is not None:  # stage 4
        rows = write_table(processed, spec.table, engine)
        db_status = f"{rows} rows loaded into table '{spec.table}'"
    else:
        db_status = "skipped (PostgreSQL unavailable)"

    _write_processing_report(run_dir, spec, report, db_status)
    return {"run_dir": str(run_dir), "processed_rows": len(processed), "db": db_status}


def run_pipeline(load_db: bool = True) -> dict:
    """Run all sources then the cross-source analysis. Returns a summary dict."""
    load_dotenv(config.PROJECT_ROOT / ".env")  # honour ANONYMIZATION_SALT + POSTGRES_*
    engine = None
    if load_db and db_engine.is_available():
        engine = db_engine.get_engine()
    elif load_db:
        logger.warning("PostgreSQL unavailable — database load SKIPPED for all sources.")

    results: dict = {}
    for spec in SOURCE_SPECS:
        results[spec.name] = run_source(spec, engine)

    logger.info("=== Cross-source analysis ===")
    results["cross_source"] = {"run_dir": str(run_cross_source())}

    logger.info("Pipeline finished: %s", ", ".join(results))
    return results
