"""Run orchestration: execute the pipeline and persist all artifacts.

This module is the single source of truth for *producing a run*. Both the CLI
(``scripts/run_incidents.py``) and notebooks call :func:`execute_run` /
:func:`run_from_env`, so the persistence logic is never duplicated.

It deliberately does NOT set the matplotlib backend: the headless ``Agg``
backend is configured by the CLI entry point, while notebooks keep their inline
backend.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from src import config
from src.common.env import load_dotenv  # re-exported for the CLI
from src.common.registry import upsert_run
from src.common.reporting import write_dataset_report as write_shared_report
from src.sources.incidents import correlations, distributions, histograms
from src.sources.incidents.pipeline import PipelineResult, run_pipeline

logger = logging.getLogger(__name__)

SOURCE_NAME = "incidents"


def generate_plots(result: PipelineResult, run_dir: Path) -> list[Path]:
    """Generate all EDA plots, in order (distributions, histograms, correlations)."""
    paths: list[Path] = []
    paths += distributions.plot_all(result.data, run_dir)  # 1.x
    paths += histograms.plot_all(result.data, run_dir)  # 2.x
    paths += correlations.plot_all(result.data, run_dir)  # 3.x
    return paths


# Ordered list of produced graphs: (filename, human-readable caption).
GRAPH_CATALOG: list[tuple[str, str]] = [
    ("1.1_dist_incidents_day.png", "Incident distribution per day"),
    ("1.2_dist_incidents_week.png", "Incident distribution per week"),
    ("1.3_dist_incidents_shift.png", "Incident distribution per shift"),
    ("2.1_hist_incidents_machine.png", "Incidents per machine"),
    ("2.2_hist_incidents_operator.png", "Incidents per operator (pseudonymised)"),
    ("2.3_hist_incidents_signal.png", "Incidents per signal"),
    ("2.4_hist_incidents_confidence.png", "Incidents per confidence index"),
    ("3.1_corr_severity_signals.png", "Correlation: severity / signals"),
    ("3.2_corr_severity_comment.png", "Correlation: severity / comment category"),
]


def write_run_report(result: PipelineResult, run_dir: Path, run_id: str, input_path) -> Path:
    """Write the run's technical markdown report."""
    out = run_dir / "run_report.md"
    m = result.metrics_source
    missing_lines = (
        "\n".join(f"| `{col}` | {n} |" for col, n in m["n_missing_per_column"].items())
        or "| _(none)_ | 0 |"
    )
    anon_lines = "\n".join(
        f"- `{col}` → {result.anonymization_report['method'][col]}"
        for col in result.anonymization_report["processed_columns"]
    )
    artifact_lines = "\n".join(f"- `{name}`" for name, _ in GRAPH_CATALOG)

    content = f"""# Run report — {run_id}

- **Source**: `{input_path}`
- **Run date**: {run_id[:4]}-{run_id[4:6]}-{run_id[6:8]} {run_id[8:10]}:{run_id[10:12]}
- **Folder**: `{run_dir.as_posix()}`

## Quality metrics (source data)

| Metric | Value |
|---|---|
| Number of rows | {m['n_rows']} |
| Number of columns | {m['n_columns']} |
| Unique machines | {m['unique_machines']} |
| Missing values (total) | {m['n_missing_total']} |

### Missing values per column

| Column | Missing |
|---|---|
{missing_lines}

## Anonymisation

{anon_lines}

## Reporting confidence index

`confidence_index = number of active signals / total number of signals`

| Statistic | Value |
|---|---|
| Mean | {result.confidence_summary.get('mean', 'n/a')} |
| Median | {result.confidence_summary.get('median', 'n/a')} |
| Min | {result.confidence_summary.get('min', 'n/a')} |
| Max | {result.confidence_summary.get('max', 'n/a')} |

## Produced artifacts

- `incidents_anonymized.csv`
{artifact_lines}
- `dataset_report.md`
"""
    out.write_text(content, encoding="utf-8")
    logger.info("Report written: %s", out.name)
    return out


def write_dataset_report(result: PipelineResult, run_dir: Path, run_id: str) -> Path:
    """Write a shareable, business-friendly synthesis report compiling all graphs."""
    df = result.data
    m = result.metrics_source

    period = "n/a"
    if config.DATE_COLUMN in df.columns:
        dates = df[config.DATE_COLUMN].dropna()
        if not dates.empty:
            period = f"{dates.min():%Y-%m-%d} → {dates.max():%Y-%m-%d}"
    n_operators = int(df["operator_name"].nunique()) if "operator_name" in df.columns else 0
    n_signals = len([c for c in config.SIGNAL_COLUMNS if c in df.columns])
    conf = result.confidence_summary

    return write_shared_report(
        run_dir,
        title="Incident dataset — synthesis report",
        subtitle=(
            f"Run `{run_id}` · shareable summary for business teams. The data is "
            "anonymised: operators are pseudonymised and cannot be re-identified."
        ),
        indicators={
            "Reporting period": period,
            "Number of incidents": m["n_rows"],
            "Unique machines": m["unique_machines"],
            "Unique operators (pseudonymised)": n_operators,
            "Signals tracked": n_signals,
            "Missing values (total)": m["n_missing_total"],
            "Mean confidence index": conf.get("mean", "n/a"),
        },
        intro=(
            "**How to read this report.** Each incident records the machine, the shift, "
            "the severity and the set of *signals* (anomaly types prefixed by `type_`) "
            "that fired. The **confidence index** of an incident is the share of signals "
            "active at once: an incident corroborated by several signals is considered "
            "more reliable than one relying on a single isolated signal."
        ),
        sections={
            "1. Temporal distributions": GRAPH_CATALOG[0:3],
            "2. Incident histograms": GRAPH_CATALOG[3:7],
            "3. Correlations": GRAPH_CATALOG[7:9],
        },
        notes=[
            "Machines and shifts concentrating the most incidents (sections 1 & 2) are "
            "natural priorities for preventive maintenance.",
            "The severity / signals correlation (3.1) highlights which signals tend to go "
            "with more severe incidents.",
            "Incidents with a low confidence index (single signal) may deserve a closer "
            "manual review.",
        ],
    )


def update_registry(result: PipelineResult, run_id: str, run_dir: Path) -> None:
    """Add (or update) the run entry in the incidents ``runs_registry.json``."""
    m = result.metrics_source
    entry = {
        "run_id": run_id,
        "folder": run_dir.relative_to(config.PROJECT_ROOT).as_posix(),
        "n_rows": m["n_rows"],
        "n_columns": m["n_columns"],
        "unique_machines": m["unique_machines"],
        "n_missing_total": m["n_missing_total"],
        "n_missing_per_column": m["n_missing_per_column"],
        "mean_confidence_index": result.confidence_summary.get("mean"),
    }
    upsert_run(config.RUNS_REGISTRY_PATH, entry)


def execute_run(
    input_path, salt: str, pseudonym_length: int = config.DEFAULT_PSEUDONYM_LENGTH
) -> Path:
    """Run the full pipeline and persist every artifact; return the run folder.

    Steps: timestamped folder → pipeline → anonymised CSV → EDA plots →
    ``run_report.md`` → ``dataset_report.md`` → ``runs_registry.json`` update.
    """
    run_id = datetime.now().strftime("%Y%m%d%H%M")
    run_dir = config.ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Run %s — folder %s", run_id, run_dir)

    result = run_pipeline(input_path, salt=salt, pseudonym_length=pseudonym_length)

    csv_path = run_dir / "incidents_anonymized.csv"
    result.data.to_csv(csv_path, index=False, encoding=config.CSV_ENCODING)
    logger.info("Anonymised dataset written: %s", csv_path.name)

    generate_plots(result, run_dir)
    write_run_report(result, run_dir, run_id, input_path)
    write_dataset_report(result, run_dir, run_id)
    update_registry(result, run_id, run_dir)

    logger.info("Run %s completed successfully.", run_id)
    return run_dir


def run_from_env(input_path=None) -> Path:
    """Convenience wrapper: load ``.env`` then :func:`execute_run`.

    Designed for notebooks: one call that reads ``ANONYMIZATION_SALT`` from
    ``.env`` and produces a full run.
    """
    load_dotenv(config.PROJECT_ROOT / ".env")
    salt = os.environ.get(config.SALT_ENV_VAR, "")
    pseudonym_length = int(
        os.environ.get(config.PSEUDONYM_LENGTH_ENV_VAR, config.DEFAULT_PSEUDONYM_LENGTH)
    )
    return execute_run(input_path or config.DEFAULT_INPUT_CSV, salt, pseudonym_length)


def run_default(input_path=None) -> Path:
    """Uniform entry point used by the multi-source orchestrator (``run_all``)."""
    return run_from_env(input_path)


def load_dataframe(input_path=None):
    """Return the anonymised, enriched DataFrame to be processed and stored.

    Anonymisation happens here (ingestion boundary) so the DB never holds PII.
    """
    load_dotenv(config.PROJECT_ROOT / ".env")
    salt = os.environ.get(config.SALT_ENV_VAR, "")
    pseudonym_length = int(
        os.environ.get(config.PSEUDONYM_LENGTH_ENV_VAR, config.DEFAULT_PSEUDONYM_LENGTH)
    )
    return run_pipeline(input_path or config.DEFAULT_INPUT_CSV, salt, pseudonym_length).data
