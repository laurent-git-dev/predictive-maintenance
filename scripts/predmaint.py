"""Unified command-line entry point for the predictive-maintenance pipeline.

Consolidates the per-source scripts into one CLI with subcommands.

Usage
-----
    uv run python scripts/predmaint.py run                 # full pipeline (+ DB load)
    uv run python scripts/predmaint.py run --no-db         # skip the PostgreSQL load
    uv run python scripts/predmaint.py source telemetry    # one source (Bronze + Silver)
    uv run python scripts/predmaint.py lineage             # latest batch lineage (needs DB)
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

from src.usecase.orchestrator import run_pipeline, run_source_by_name  # noqa: E402
from src.usecase.sources.registry import SOURCE_SPECS  # noqa: E402

# Readable accented logs in the Windows console (cp1252 by default).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("predmaint")

_SOURCE_NAMES = [s.name for s in SOURCE_SPECS]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="predmaint", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser(
        "run", help="Run the full multi-source pipeline (+ Gold + cross-source)."
    )
    p_run.add_argument("--no-db", action="store_true", help="Skip the PostgreSQL load stage.")

    p_src = sub.add_parser("source", help="Run a single source (Bronze + Silver).")
    p_src.add_argument("name", choices=_SOURCE_NAMES, help="Source to run.")
    p_src.add_argument("--no-db", action="store_true", help="Skip the PostgreSQL load stage.")

    sub.add_parser("lineage", help="Print the latest batch lineage from meta.processing_runs.")
    return parser


def _cmd_lineage() -> int:
    from src.framework.db.engine import get_engine, is_available
    from src.framework.lineage.tracker import lineage_markdown

    if not is_available():
        logger.error("PostgreSQL not available — no lineage to show.")
        return 1
    print(lineage_markdown(get_engine()))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "run":
            run_pipeline(load_db=not args.no_db)
        elif args.command == "source":
            run_source_by_name(args.name, load_db=not args.no_db)
        elif args.command == "lineage":
            return _cmd_lineage()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s failed: %s", args.command, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
