"""CLI entry point for the incidents ingestion pipeline.

Usage
-----
    uv run python scripts/run_ingestion.py --input data/raw/incidents.csv

Thin wrapper around :func:`src.ingestion.runner.execute_run`: it parses the CLI
arguments, loads the secret salt from ``.env`` and configures a headless
matplotlib backend. The actual orchestration lives in ``src/ingestion/runner.py``
so it can be reused from notebooks.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Make the `src` package importable regardless of the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Headless backend for the CLI (no display): must be set before pyplot is
# imported through the visualization modules.
import matplotlib  # noqa: E402

matplotlib.use("Agg")

from src import config  # noqa: E402
from src.ingestion.runner import execute_run, load_dotenv  # noqa: E402

# Readable accented logs in the Windows console (cp1252 by default).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_ingestion")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incidents ingestion pipeline.")
    parser.add_argument(
        "--input",
        type=Path,
        default=config.DEFAULT_INPUT_CSV,
        help="Path to the source CSV (default: data/raw/incidents.csv).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(config.PROJECT_ROOT / ".env")

    salt = os.environ.get(config.SALT_ENV_VAR, "")
    pseudonym_length = int(
        os.environ.get(config.PSEUDONYM_LENGTH_ENV_VAR, config.DEFAULT_PSEUDONYM_LENGTH)
    )

    try:
        execute_run(args.input, salt=salt, pseudonym_length=pseudonym_length)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Run failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
