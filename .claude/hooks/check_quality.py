"""Stop hook: lint + unit-test gate when Python files changed this session.

Runs only if there are uncommitted ``*.py`` changes (so trivial/conversational turns are not
slowed down). Runs ``ruff check`` + the **unit** tests (``-m "not golden"`` — fast, no data
load). On failure it blocks the stop once (exit 2) and feeds the summary back so Claude can
fix; the ``stop_hook_active`` flag prevents an infinite loop on the next stop.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

TARGETS = ["src", "scripts", "tests", "conftest.py"]


def _last_line(text: str, default: str) -> str:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else default


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("stop_hook_active"):
        sys.exit(0)  # already nudged once — let the stop go through

    root = os.environ.get("CLAUDE_PROJECT_DIR", ".")

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True
    )
    changed_py = [ln for ln in status.stdout.splitlines() if ln.rstrip().endswith(".py")]
    if not changed_py:
        sys.exit(0)  # no code changes -> nothing to gate

    problems = []
    ruff = subprocess.run(
        ["ruff", "check", *TARGETS], cwd=root, capture_output=True, text=True
    )
    if ruff.returncode != 0:
        problems.append("ruff: " + _last_line(ruff.stdout, "check failed"))

    tests = subprocess.run(
        ["pytest", "-q", "-m", "not golden"], cwd=root, capture_output=True, text=True
    )
    if tests.returncode != 0:
        problems.append("pytest: " + _last_line(tests.stdout, "unit tests failed"))

    if problems:
        print("Quality gate FAILED → " + " | ".join(problems), file=sys.stderr)
        sys.exit(2)  # block the stop once; Claude gets the summary to act on

    sys.exit(0)


if __name__ == "__main__":
    main()
