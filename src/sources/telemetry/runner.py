"""Telemetry run orchestration: load, plot per-machine boxplots, report, registry.

Single source of truth for producing a telemetry run, reused by the CLI
(``scripts/run_telemetry.py``) and notebooks. Does not set the matplotlib
backend (the CLI sets the headless Agg backend).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config
from src.common.metrics import compute_quality_metrics  # generic, reused
from src.common.registry import upsert_run
from src.common.reporting import write_dataset_report as write_shared_report
from src.sources.telemetry import boxplots
from src.sources.telemetry.loader import load_telemetry

logger = logging.getLogger(__name__)

SOURCE_NAME = "telemetry"

# Ordered list of produced graphs: (filename, caption). Mirrors boxplots naming.
GRAPH_CATALOG: list[tuple[str, str]] = [
    (f"1.{i}_box_{param}.png", f"{param} by machine")
    for i, param in enumerate(config.TELEMETRY_PARAM_COLUMNS, start=1)
]


def _reporting_period(df: pd.DataFrame) -> str:
    """Return the timestamp range as a readable string."""
    col = config.TELEMETRY_TIMESTAMP_COLUMN
    if col in df.columns and df[col].notna().any():
        ts = df[col].dropna()
        return f"{ts.min():%Y-%m-%d %H:%M} → {ts.max():%Y-%m-%d %H:%M}"
    return "n/a"


def write_run_report(df, metrics: dict, run_dir: Path, run_id: str, input_path, graphs) -> Path:
    """Write the telemetry run's markdown report."""
    out = run_dir / "run_report.md"
    missing_lines = (
        "\n".join(f"| `{col}` | {n} |" for col, n in metrics["n_missing_per_column"].items())
        or "| _(none)_ | 0 |"
    )
    param_stats = (
        df[[c for c in config.TELEMETRY_PARAM_COLUMNS if c in df.columns]]
        .describe()
        .T[["mean", "std", "min", "max"]]
        .round(2)
    )
    stats_lines = "\n".join(
        f"| `{p}` | {r['mean']} | {r['std']} | {r['min']} | {r['max']} |"
        for p, r in param_stats.iterrows()
    )
    artifact_lines = "\n".join(f"- `{p.name}`" for p in graphs)

    content = f"""# Telemetry run report — {run_id}

- **Source**: `{input_path}`
- **Run date**: {run_id[:4]}-{run_id[4:6]}-{run_id[6:8]} {run_id[8:10]}:{run_id[10:12]}
- **Folder**: `{run_dir.as_posix()}`
- **Reporting period**: {_reporting_period(df)}

## Quality metrics

| Metric | Value |
|---|---|
| Number of rows | {metrics['n_rows']} |
| Number of columns | {metrics['n_columns']} |
| Unique machines | {metrics['unique_machines']} |
| Missing values (total) | {metrics['n_missing_total']} |

### Missing values per column

| Column | Missing |
|---|---|
{missing_lines}

## Parameter statistics

| Parameter | Mean | Std | Min | Max |
|---|---|---|---|---|
{stats_lines}

## Produced artifacts

{artifact_lines}
"""
    out.write_text(content, encoding="utf-8")
    logger.info("Report written: %s", out.name)
    return out


def update_registry(metrics: dict, run_id: str, run_dir: Path, period: str) -> None:
    """Add (or update) the run entry in the telemetry ``runs_registry.json``."""
    entry = {
        "run_id": run_id,
        "folder": run_dir.relative_to(config.PROJECT_ROOT).as_posix(),
        "n_rows": metrics["n_rows"],
        "n_columns": metrics["n_columns"],
        "unique_machines": metrics["unique_machines"],
        "n_missing_total": metrics["n_missing_total"],
        "n_missing_per_column": metrics["n_missing_per_column"],
        "reporting_period": period,
    }
    upsert_run(config.TELEMETRY_RUNS_REGISTRY_PATH, entry)


def write_dataset_report(df, metrics: dict, run_dir: Path, run_id: str) -> Path:
    """Write the shareable, business-friendly synthesis report for telemetry."""
    n_params = len([c for c in config.TELEMETRY_PARAM_COLUMNS if c in df.columns])
    return write_shared_report(
        run_dir,
        title="Machine telemetry — synthesis report",
        subtitle=f"Run `{run_id}` · shareable summary for business teams.",
        indicators={
            "Reporting period": _reporting_period(df),
            "Number of records": metrics["n_rows"],
            "Unique machines": metrics["unique_machines"],
            "Parameters tracked": n_params,
            "Missing values (total)": metrics["n_missing_total"],
        },
        intro=(
            "**How to read this report.** Each row is an hourly reading per machine. "
            "Each boxplot shows the distribution of one parameter across machines "
            "(median, spread, range) — useful to spot machines that run hotter, faster "
            "or more variably than their peers."
        ),
        sections={"1. Parameter distributions by machine": GRAPH_CATALOG},
        notes=[
            "Machines whose boxplots sit clearly above or below their peers may indicate "
            "drift or miscalibration worth investigating.",
            "Wide boxes (high variability) can signal unstable operating conditions.",
        ],
    )


def execute_run(input_path) -> Path:
    """Run the telemetry pipeline and persist artifacts; return the run folder."""
    run_id = datetime.now().strftime("%Y%m%d%H%M")
    run_dir = config.TELEMETRY_ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Telemetry run %s — folder %s", run_id, run_dir)

    df = load_telemetry(input_path)
    metrics = compute_quality_metrics(df)

    graphs = boxplots.plot_all(df, run_dir)
    write_run_report(df, metrics, run_dir, run_id, input_path, graphs)
    write_dataset_report(df, metrics, run_dir, run_id)
    update_registry(metrics, run_id, run_dir, _reporting_period(df))

    logger.info("Telemetry run %s completed successfully.", run_id)
    return run_dir


def run_telemetry(input_path=None) -> Path:
    """Convenience wrapper for notebooks: run on the default (or given) CSV."""
    return execute_run(input_path or config.DEFAULT_TELEMETRY_CSV)


def run_default(input_path=None) -> Path:
    """Uniform entry point used by the multi-source orchestrator (``run_all``)."""
    return run_telemetry(input_path)


def load_dataframe(input_path=None):
    """Return the telemetry DataFrame to be processed and stored."""
    return load_telemetry(input_path or config.DEFAULT_TELEMETRY_CSV)
