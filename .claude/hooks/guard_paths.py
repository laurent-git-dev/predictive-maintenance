"""PreToolUse guard: block writes to protected paths (data/raw, .env).

Enforces the data-security rule from CLAUDE.md (never modify/commit raw data or secrets).
Best-effort: a guard, not a sandbox. Fails *open* on unexpected input so a parsing glitch
never bricks every tool call; blocks (exit 2) only on a clear protected-path write.
"""

from __future__ import annotations

import json
import re
import sys

# Path fragments that must never be written to / committed.
PROTECTED = r"(data/raw|data\\raw|\.env)"

# Bash commands considered destructive (delete / move / overwrite) on a protected path.
# Note: ``git add`` is intentionally NOT blocked — raw CSVs are already gitignored and the
# DVC ``*.dvc`` pointers living under data/raw/ must stay committable.
BASH_BLOCKERS = [
    rf"\b(rm|mv|rmdir|truncate)\b[^|&;]*{PROTECTED}",  # delete / move / truncate
    rf"(>>?|tee)\s+[^|&;]*{PROTECTED}",  # redirection that overwrites a protected path
]


def _is_protected_file(path: str) -> bool:
    p = path.replace("\\", "/")
    return "data/raw/" in p or p.endswith("/.env") or p.endswith(".env") or p == ".env"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail open

    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}

    if tool in ("Edit", "Write", "MultiEdit"):
        fp = ti.get("file_path", "")
        if fp and _is_protected_file(fp):
            print(
                f"Blocked: '{fp}' is protected (data/raw or .env must never be modified "
                "or committed — see CLAUDE.md). Edit a copy or .env.example instead.",
                file=sys.stderr,
            )
            sys.exit(2)
    elif tool == "Bash":
        cmd = ti.get("command", "")
        for pat in BASH_BLOCKERS:
            if re.search(pat, cmd, flags=re.IGNORECASE):
                print(
                    "Blocked: this command appears to modify or stage a protected path "
                    "(data/raw or .env). Raw data is DVC-tracked and secrets stay out of git.",
                    file=sys.stderr,
                )
                sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
