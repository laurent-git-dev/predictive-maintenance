"""CLI entry point for the incidents ingestion pipeline.

Usage
-----
    uv run python scripts/run_ingestion.py --input data/raw/incidents.csv

The script creates a timestamped folder ``artifacts/ingestions/incidents/AAAAMMJJHHMM/``,
writes the anonymised dataset, the EDA plots and a ``run_report.md``, then updates
the ``runs_registry.json`` registry.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Make the `src` package importable regardless of the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config  # noqa: E402
from src.ingestion.pipeline import PipelineResult, run_pipeline  # noqa: E402
from src.visualization import correlations, distributions, histograms  # noqa: E402

# Readable accented logs in the Windows console (cp1252 by default).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_ingestion")


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incidents ingestion pipeline.")
    parser.add_argument(
        "--input",
        type=Path,
        default=config.DEFAULT_INPUT_CSV,
        help="Path to the source CSV (default: data/raw/incidents.csv).",
    )
    return parser.parse_args()


def generate_plots(result: PipelineResult, run_dir: Path) -> list[Path]:
    """Generate all EDA plots in the run folder."""
    paths = distributions.plot_all(result.data, run_dir)
    paths.append(histograms.plot_signals_by_machine(result.data, run_dir))
    paths.append(correlations.plot_correlation_matrix(result.data, run_dir))
    return paths


def write_run_report(result: PipelineResult, run_dir: Path, run_id: str, input_path: Path) -> Path:
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


def main() -> int:
    args = parse_args()
    load_dotenv(config.PROJECT_ROOT / ".env")

    salt = os.environ.get(config.SALT_ENV_VAR, "")
    pseudonym_length = int(
        os.environ.get(config.PSEUDONYM_LENGTH_ENV_VAR, config.DEFAULT_PSEUDONYM_LENGTH)
    )

    run_id = datetime.now().strftime("%Y%m%d%H%M")
    run_dir = config.ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Run %s — folder %s", run_id, run_dir)

    try:
        result = run_pipeline(args.input, salt=salt, pseudonym_length=pseudonym_length)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Run failed: %s", exc)
        return 1

    # Anonymised dataset.
    csv_path = run_dir / "incidents_anonymized.csv"
    result.data.to_csv(csv_path, index=False, encoding=config.CSV_ENCODING)
    logger.info("Anonymised dataset written: %s", csv_path.name)

    generate_plots(result, run_dir)
    write_run_report(result, run_dir, run_id, args.input)
    update_registry(result, run_id, run_dir)

    logger.info("Run %s completed successfully.", run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
