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
import json
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

    p_gold = sub.add_parser("gold", help="Build a versioned Gold dataset from a params profile.")
    p_gold.add_argument("--params", default=None, help="YAML profile with a gold: section.")
    p_gold.add_argument("--no-db", action="store_true", help="Build from in-memory Silver.")

    sub.add_parser("lineage", help="Print the latest batch lineage from meta.processing_runs.")
    return parser


def _cmd_gold(params_path: str | None, no_db: bool) -> int:
    import yaml

    from src.framework.db.engine import get_engine, is_available
    from src.settings import require_salt
    from src.usecase.gold.experiment import build_gold_version, load_silver

    require_salt()
    params = None
    if params_path:
        params = (yaml.safe_load(Path(params_path).read_text(encoding="utf-8")) or {}).get("gold")
    engine = get_engine() if (not no_db and is_available()) else None
    silver = load_silver(engine)
    out_dir = config.PROJECT_ROOT / "artifacts" / "gold_experiments"
    _, manifest = build_gold_version(silver, params, output_dir=out_dir)
    summary = {
        k: manifest[k]
        for k in ("dataset_version", "rows", "cols", "content_hash", "split", "label_positive_rate")
    }
    print(json.dumps(summary, indent=2))
    logger.info("Gold version %s written under %s", manifest["dataset_version"], out_dir)
    return 0


def _cmd_lineage() -> int:
    from src.framework.db.engine import get_engine, is_available
    from src.framework.lineage.dashboard import lineage_dashboard_markdown
    from src.framework.lineage.tracker import lineage_markdown

    if not is_available():
        logger.error("PostgreSQL not available — no lineage to show.")
        return 1
    engine = get_engine()
    print("## Batches\n")
    print(lineage_dashboard_markdown(engine))
    print("\n## Latest batch — steps\n")
    print(lineage_markdown(engine))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "run":
            run_pipeline(load_db=not args.no_db)
        elif args.command == "source":
            run_source_by_name(args.name, load_db=not args.no_db)
        elif args.command == "gold":
            return _cmd_gold(args.params, args.no_db)
        elif args.command == "lineage":
            return _cmd_lineage()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s failed: %s", args.command, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
