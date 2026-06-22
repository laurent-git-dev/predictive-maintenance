"""CLI entry point for the cross-source analysis.

Usage
-----
    uv run python scripts/run_cross_source.py

Joins the incidents, telemetry and machines sources and produces cross-source
graphs + report in ``artifacts/analyses/cross_source/AAAAMMJJHHMM/``. The
orchestration lives in ``src/analyses/runner.py`` so it can be reused from
notebooks.
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

from src.usecase.analyses.runner import execute_run  # noqa: E402

# Readable accented logs in the Windows console (cp1252 by default).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_cross_source")


def main() -> int:
    try:
        execute_run()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Run failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
