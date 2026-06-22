"""CLI entry point for the incidents source (Bronze + Silver layers).

Usage
-----
    uv run python scripts/run_incidents.py
    uv run python scripts/run_incidents.py --no-db

Produces the per-feature understanding (reports + graphs) for the bronze and silver
layers and loads them into the ``bronze`` / ``silver`` PostgreSQL schemas.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

from src.usecase.orchestrator import run_source_by_name  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_incidents")


def main() -> int:
    parser = argparse.ArgumentParser(description="Incidents source (bronze + silver).")
    parser.add_argument("--no-db", action="store_true", help="Skip the PostgreSQL load stage.")
    args = parser.parse_args()
    try:
        run_source_by_name("incidents", load_db=not args.no_db)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Run failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
