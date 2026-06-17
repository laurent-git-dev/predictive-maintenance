"""CLI entry point for the full multi-source pipeline.

Usage
-----
    uv run python scripts/run_pipeline.py            # all sources + cross-source
    uv run python scripts/run_pipeline.py --no-db    # skip the database load

For each source: ingestion + understanding (reports/graphs) + processing
(processed.csv) + load into PostgreSQL; then the cross-source analysis.
Re-run the same command after any data update — DB tables are fully reloaded.
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

from src.orchestrator import run_pipeline  # noqa: E402

# Readable accented logs in the Windows console (cp1252 by default).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_pipeline")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full multi-source ingestion pipeline.")
    parser.add_argument("--no-db", action="store_true", help="Skip the PostgreSQL load stage.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_pipeline(load_db=not args.no_db)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Pipeline failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
