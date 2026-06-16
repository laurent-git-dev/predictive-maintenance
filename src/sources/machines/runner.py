"""Machines/maintenance run orchestration: load SQL, plot, report, registry.

Single source of truth for producing a machines run, reused by the CLI
(``scripts/run_machines.py``) and notebooks. Does not set the matplotlib backend
(the CLI sets the headless Agg backend).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config
from src.common.metrics import compute_quality_metrics
from src.common.registry import upsert_run
from src.sources.machines import plots
from src.sources.machines.loader import build_engine, load_maintenance

logger = logging.getLogger(__name__)

SOURCE_NAME = "machines"

GRAPH_CATALOG: list[tuple[str, str]] = [
    ("1.1_hist_maintenance_machine.png", "Maintenance events per machine"),
    ("1.2_box_duration_machine.png", "Maintenance duration by machine"),
    ("1.3_maintenance_type_split.png", "Proactive vs reactive per machine"),
    ("1.4_hist_maintenance_component.png", "Maintenance events per component"),
]


def _reporting_period(df: pd.DataFrame) -> str:
    col = config.MAINTENANCE_TIMESTAMP_COLUMN
    if col in df.columns and df[col].notna().any():
        ts = df[col].dropna()
        return f"{ts.min():%Y-%m-%d} → {ts.max():%Y-%m-%d}"
    return "n/a"


def write_run_report(df, metrics: dict, run_dir: Path, run_id: str, input_path) -> Path:
    """Write the machines run's markdown report."""
    out = run_dir / "run_report.md"
    type_counts = df[config.MAINTENANCE_TYPE_COLUMN].value_counts().to_dict()
    type_lines = "\n".join(f"| `{k}` | {v} |" for k, v in type_counts.items()) or "| _(none)_ | 0 |"
    n_linked = int(df[config.MAINTENANCE_INCIDENT_COLUMN].notna().sum())
    mean_duration = round(float(df[config.MAINTENANCE_DURATION_COLUMN].mean()), 2)
    n_components = int(df[config.MAINTENANCE_COMPONENT_COLUMN].nunique())
    artifact_lines = "\n".join(f"- `{name}`" for name, _ in GRAPH_CATALOG)

    content = f"""# Machines / maintenance run report — {run_id}

- **Source**: `{input_path}`
- **Run date**: {run_id[:4]}-{run_id[4:6]}-{run_id[6:8]} {run_id[8:10]}:{run_id[10:12]}
- **Folder**: `{run_dir.as_posix()}`
- **Reporting period**: {_reporting_period(df)}

## Quality metrics

| Metric | Value |
|---|---|
| Number of maintenance events | {metrics['n_rows']} |
| Number of columns | {metrics['n_columns']} |
| Unique machines | {metrics['unique_machines']} |
| Missing values (total) | {metrics['n_missing_total']} |

## Maintenance summary

| Indicator | Value |
|---|---|
| Mean duration (hours) | {mean_duration} |
| Distinct components | {n_components} |
| Events linked to an incident | {n_linked} |

### By type

| Type | Count |
|---|---|
{type_lines}

## Produced artifacts

{artifact_lines}
"""
    out.write_text(content, encoding="utf-8")
    logger.info("Report written: %s", out.name)
    return out


def update_registry(metrics: dict, run_id: str, run_dir: Path, period: str) -> None:
    """Add (or update) the run entry in the machines ``runs_registry.json``."""
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
    upsert_run(config.MACHINES_RUNS_REGISTRY_PATH, entry)


def execute_run(input_path) -> Path:
    """Run the machines pipeline and persist artifacts; return the run folder."""
    run_id = datetime.now().strftime("%Y%m%d%H%M")
    run_dir = config.MACHINES_ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Machines run %s — folder %s", run_id, run_dir)

    engine = build_engine(input_path)
    df = load_maintenance(engine)
    metrics = compute_quality_metrics(df)

    plots.plot_all(df, run_dir)
    write_run_report(df, metrics, run_dir, run_id, input_path)
    update_registry(metrics, run_id, run_dir, _reporting_period(df))

    logger.info("Machines run %s completed successfully.", run_id)
    return run_dir


def run_default(input_path=None) -> Path:
    """Uniform entry point used by the multi-source orchestrator (``run_all``)."""
    return execute_run(input_path or config.DEFAULT_MACHINES_SQL)
