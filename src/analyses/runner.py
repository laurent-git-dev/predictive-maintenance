"""Cross-source analysis orchestration: join sources, plot, report, registry.

Single source of truth for producing a cross-source run, reused by the CLI
(``scripts/run_cross_source.py``) and notebooks. Does not set the matplotlib
backend (the CLI sets the headless Agg backend).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from src import config
from src.analyses import plots
from src.analyses.joins import (
    build_machine_profile,
    build_reactive_incident_join,
    load_sources,
)
from src.common.registry import upsert_run
from src.common.reporting import write_dataset_report as write_shared_report

logger = logging.getLogger(__name__)

ANALYSIS_NAME = "cross_source"

GRAPH_CATALOG: list[tuple[str, str]] = [
    ("1_incidents_vs_maintenance.png", "Incidents vs maintenance per machine"),
    ("2_reactive_vs_severity.png", "Reactive maintenance vs incident severity"),
    ("3_telemetry_vs_incidents.png", "Mean temperature vs incidents per machine"),
]


def write_run_report(profile, reactive_join, run_dir: Path, run_id: str) -> Path:
    """Write the cross-source run's markdown report."""
    out = run_dir / "run_report.md"
    artifact_lines = "\n".join(f"- `{name}`" for name, _ in GRAPH_CATALOG)

    corr_lines = []
    for col in ["mean_temperature_c", "mean_pressure_bar", "n_maintenance", "mean_confidence"]:
        if col in profile.columns:
            c = profile[[col, "n_incidents"]].corr().iloc[0, 1]
            corr_lines.append(f"| `{col}` vs `n_incidents` | {c:.2f} |")
    corr_md = "\n".join(corr_lines) or "| _(n/a)_ | n/a |"

    content = f"""# Cross-source analysis report — {run_id}

- **Run date**: {run_id[:4]}-{run_id[4:6]}-{run_id[6:8]} {run_id[8:10]}:{run_id[10:12]}
- **Folder**: `{run_dir.as_posix()}`
- **Sources joined**: incidents · telemetry · machines (maintenance)

## Scope

- Machines profiled: {len(profile)}
- Reactive maintenances linked to an incident: {len(reactive_join)}

## Correlations with incident count (per machine)

| Pair | Pearson r |
|---|---|
{corr_md}

## Produced artifacts

- `machine_profile.csv`
{artifact_lines}
"""
    out.write_text(content, encoding="utf-8")
    logger.info("Report written: %s", out.name)
    return out


def update_registry(profile, reactive_join, run_id: str, run_dir: Path) -> None:
    """Add (or update) the run entry in the cross-source ``runs_registry.json``."""
    entry = {
        "run_id": run_id,
        "folder": run_dir.relative_to(config.PROJECT_ROOT).as_posix(),
        "n_machines": int(len(profile)),
        "n_reactive_linked": int(len(reactive_join)),
        "sources": ["incidents", "telemetry", "machines"],
    }
    upsert_run(config.CROSS_SOURCE_RUNS_REGISTRY_PATH, entry)


def write_dataset_report(profile, reactive_join, run_dir: Path, run_id: str) -> Path:
    """Write the shareable, business-friendly cross-source synthesis report."""
    indicators = {
        "Machines profiled": len(profile),
        "Reactive maintenances linked to an incident": len(reactive_join),
        "Sources joined": "incidents · telemetry · machines",
    }
    for col, label in [
        ("mean_temperature_c", "Corr. mean temperature ↔ incidents"),
        ("n_maintenance", "Corr. maintenance count ↔ incidents"),
    ]:
        if col in profile.columns:
            indicators[label] = round(float(profile[[col, "n_incidents"]].corr().iloc[0, 1]), 2)

    return write_shared_report(
        run_dir,
        title="Cross-source synthesis report",
        subtitle=f"Run `{run_id}` · cross-source summary for business teams.",
        indicators=indicators,
        intro=(
            "**How to read this report.** The sources are joined per machine (and per "
            "incident for the maintenance link). These views relate incidents, telemetry "
            "and maintenance to surface which machines and conditions drive failures."
        ),
        sections={"Cross-source relationships": GRAPH_CATALOG},
        notes=[
            "Machines high on both incidents and maintenance are the clearest preventive "
            "targets.",
            "A positive temperature ↔ incidents correlation would support temperature-based "
            "early-warning thresholds.",
            "Reactive maintenances are all linked to an incident — a basis for a future "
            "predictive model.",
        ],
    )


def execute_run() -> Path:
    """Build the cross-source analyses and persist artifacts; return the run folder."""
    run_id = datetime.now().strftime("%Y%m%d%H%M")
    run_dir = config.CROSS_SOURCE_ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Cross-source run %s — folder %s", run_id, run_dir)

    sources = load_sources()
    profile = build_machine_profile(sources)
    reactive_join = build_reactive_incident_join(sources)

    profile.to_csv(run_dir / "machine_profile.csv", index=False, encoding=config.CSV_ENCODING)
    plots.plot_all(profile, reactive_join, run_dir)
    write_run_report(profile, reactive_join, run_dir, run_id)
    write_dataset_report(profile, reactive_join, run_dir, run_id)
    update_registry(profile, reactive_join, run_id, run_dir)

    logger.info("Cross-source run %s completed successfully.", run_id)
    return run_dir


def run_default() -> Path:
    """Uniform entry point (mirrors the source runners)."""
    return execute_run()
