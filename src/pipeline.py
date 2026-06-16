"""Multi-source orchestrator: run every registered source in one go.

Each source exposes a uniform ``run_default() -> Path`` entry point in its
``runner`` module. To add a source, register its runner in :data:`SOURCES`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.sources.incidents import runner as incidents_runner
from src.sources.machines import runner as machines_runner
from src.sources.telemetry import runner as telemetry_runner

logger = logging.getLogger(__name__)

# Registry of sources: name -> uniform run entry point.
SOURCES: dict = {
    incidents_runner.SOURCE_NAME: incidents_runner.run_default,
    telemetry_runner.SOURCE_NAME: telemetry_runner.run_default,
    machines_runner.SOURCE_NAME: machines_runner.run_default,
}


def run_all_sources() -> dict[str, Path]:
    """Run every registered source; return a mapping name -> run folder."""
    results: dict[str, Path] = {}
    for name, run in SOURCES.items():
        logger.info("=== Running source: %s ===", name)
        results[name] = run()
    logger.info("All sources completed: %s", ", ".join(results))
    return results
