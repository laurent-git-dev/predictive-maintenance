"""CLI entry point for the machines / maintenance ingestion pipeline.

Usage
-----
    uv run python scripts/run_machines.py --input data/raw/machines.sql

Thin wrapper around :func:`src.sources.machines.runner.execute_run`: it parses
the CLI arguments and configures a headless matplotlib backend. The orchestration
lives in ``src/sources/machines/runner.py`` so it can be reused from notebooks.
"""

from __future__ import annotations

import argparse
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

from src import config  # noqa: E402
from src.sources.machines.runner import execute_run  # noqa: E402

# Readable accented logs in the Windows console (cp1252 by default).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_machines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Machines / maintenance ingestion pipeline.")
    parser.add_argument(
        "--input",
        type=Path,
        default=config.DEFAULT_MACHINES_SQL,
        help="Path to the source SQL dump (default: data/raw/machines.sql).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        execute_run(args.input)
    except FileNotFoundError as exc:
        logger.error("Run failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
