"""CLI entry point to run all data-source pipelines in one go.

Usage
-----
    uv run python scripts/run_all.py

Runs every source registered in ``src/pipeline.py`` (incidents, telemetry, …),
each producing its own artifacts and updating its own registry.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Make the `src` package importable regardless of the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Headless backend for the CLI (no display): set before pyplot is imported.
import matplotlib  # noqa: E402

matplotlib.use("Agg")

from src.pipeline import run_all_sources  # noqa: E402

# Readable accented logs in the Windows console (cp1252 by default).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_all")


def main() -> int:
    try:
        results = run_all_sources()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Pipeline failed: %s", exc)
        return 1
    for name, run_dir in results.items():
        logger.info("%s -> %s", name, run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
