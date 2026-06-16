"""Run orchestration: execute the pipeline and persist all artifacts.

This module is the single source of truth for *producing a run*. Both the CLI
(``scripts/run_ingestion.py``) and notebooks call :func:`execute_run` /
:func:`run_from_env`, so the persistence logic is never duplicated.

It deliberately does NOT set the matplotlib backend: the headless ``Agg``
backend is configured by the CLI entry point, while notebooks keep their inline
backend.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from src import config
from src.ingestion.pipeline import PipelineResult, run_pipeline
from src.visualization import correlations, distributions, histograms

logger = logging.getLogger(__name__)


def load_dotenv(path: Path) -> None:
    """Load variables from a ``.env`` file into ``os.environ`` (minimal parser)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def generate_plots(result: PipelineResult, run_dir: Path) -> list[Path]:
    """Generate all EDA plots in the run folder."""
    paths = distributions.plot_all(result.data, run_dir)
    paths.append(histograms.plot_signals_by_machine(result.data, run_dir))
    paths.append(correlations.plot_correlation_matrix(result.data, run_dir))
    return paths


def write_run_report(result: PipelineResult, run_dir: Path, run_id: str, input_path) -> Path:
    """Write the run's markdown report."""
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
- `dist_incidents_day.png`
- `dist_incidents_week.png`
- `dist_incidents_shift.png`
- `hist_signals_machine.png`
- `corr_incidents_signals.png`
"""
    out.write_text(content, encoding="utf-8")
    logger.info("Report written: %s", out.name)
    return out


def update_registry(result: PipelineResult, run_id: str, run_dir: Path) -> None:
    """Add (or update) the run entry in ``runs_registry.json``."""
    registry_path = config.RUNS_REGISTRY_PATH
    registry: dict = {"runs": []}
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Unreadable registry, resetting.")

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
    registry.setdefault("runs", [])
    registry["runs"] = [r for r in registry["runs"] if r.get("run_id") != run_id]
    registry["runs"].append(entry)
    registry["runs"].sort(key=lambda r: r["run_id"])

    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Registry updated: %s (%d runs)", registry_path.name, len(registry["runs"]))


def execute_run(
    input_path, salt: str, pseudonym_length: int = config.DEFAULT_PSEUDONYM_LENGTH
) -> Path:
    """Run the full pipeline and persist every artifact; return the run folder.

    Steps: timestamped folder → pipeline → anonymised CSV → EDA plots →
    ``run_report.md`` → ``runs_registry.json`` update.

    Parameters
    ----------
    input_path : str | pathlib.Path
        Path to the source CSV.
    salt : str
        Secret anonymisation salt.
    pseudonym_length : int, optional
        Length of the ``operator_name`` pseudonym.
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
