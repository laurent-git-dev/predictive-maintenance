"""PostToolUse hook: auto-format the Python file just edited (ruff --fix, then black).

Keeps the ruff + black (line 100) convention satisfied without thinking about it. Runs inside
the uv environment (invoked via ``uv run python``), so ``ruff`` / ``black`` are on PATH.
Best-effort and non-blocking: any failure is swallowed (exit 0).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    fp = (data.get("tool_input", {}) or {}).get("file_path", "")
    if not fp.endswith(".py") or not os.path.exists(fp):
        sys.exit(0)

    for cmd in (["ruff", "check", "--fix", "--quiet", fp], ["black", "--quiet", fp]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=60)
        except Exception:
            pass  # never block the edit on a formatter hiccup

    sys.exit(0)


if __name__ == "__main__":
    main()
