"""Generic medallion-layer runner: per-feature understanding + reports + DB load.

Used identically for every (source, layer) pair (bronze, silver, …) so the output
is uniform. Sources only provide the DataFrame and the numeric features to graph.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src import config
from src.common import profiling
from src.common.metrics import compute_quality_metrics
from src.common.reporting import write_dataset_report
from src.database.loader import write_table

logger = logging.getLogger(__name__)


def _write_run_report(df, metrics: dict, stage_dir: Path, source: str, layer: str, graphs) -> None:
    """Write a uniform technical run report for one layer."""
    missing_lines = (
        "\n".join(f"| `{c}` | {n} |" for c, n in metrics["n_missing_per_column"].items())
        or "| _(none)_ | 0 |"
    )
    artifact_lines = "\n".join(f"- `{p.name}`" for p in graphs) or "- _(none)_"
    content = f"""# {source} — {layer} run report

| Metric | Value |
|---|---|
| Rows | {metrics['n_rows']} |
| Columns | {metrics['n_columns']} |
| Unique machines | {metrics['unique_machines']} |
| Missing values (total) | {metrics['n_missing_total']} |

## Missing values per column

| Column | Missing |
|---|---|
{missing_lines}

## Produced artifacts

{artifact_lines}
"""
    (stage_dir / "run_report.md").write_text(content, encoding="utf-8")


def run_layer(
    df: pd.DataFrame,
    *,
    source: str,
    layer: str,
    run_dir: Path,
    numeric_features: list[str],
    machine_col: str,
    table: str,
    schema: str,
    engine=None,
) -> dict:
    """Produce a layer's per-feature understanding + reports, and load it to the DB.

    Returns a status dict (rows + DB outcome).
    """
    stage_dir = Path(run_dir) / layer
    stage_dir.mkdir(parents=True, exist_ok=True)
    logger.info("=== %s · %s layer ===", source, layer)

    metrics = compute_quality_metrics(df)
    graphs, body = profiling.per_feature_understanding(df, numeric_features, stage_dir, machine_col)

    write_dataset_report(
        stage_dir,
        title=f"{source} — {layer} dataset report",
        subtitle=f"{layer.capitalize()} layer · per-feature understanding.",
        indicators={
            "Layer": layer,
            "Rows": metrics["n_rows"],
            "Columns": metrics["n_columns"],
            "Unique machines": metrics["unique_machines"],
            "Missing values (total)": metrics["n_missing_total"],
        },
        intro=(
            "**How to read this report.** Each feature shows a type-aware synthesis "
            "(range, missing, spread, skew, outliers, top values…) and, for numeric "
            "features, a boxplot across machines and its distribution (histogram + KDE)."
        ),
        extra_markdown=body,
        sections={},
        notes=[
            "High `pct_missing` or `n_outliers_iqr` flags columns to clean in Silver "
            "(imputation / outliers, configured in src/sources/registry.py).",
            "Compare Bronze vs Silver to see the effect of the treatment.",
        ],
    )
    _write_run_report(df, metrics, stage_dir, source, layer, graphs)

    df.to_csv(stage_dir / f"{source}.csv", index=False, encoding=config.CSV_ENCODING)

    if engine is not None:
        rows = write_table(df, table, engine, schema)
        db_status = f"{rows} rows -> {schema}.{table}"
    else:
        db_status = "skipped (PostgreSQL unavailable)"

    logger.info("%s · %s done (%d rows, %s).", source, layer, metrics["n_rows"], db_status)
    return {"rows": metrics["n_rows"], "db": db_status}
