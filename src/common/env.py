"""Minimal ``.env`` loader (no external dependency)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def load_dotenv(path: Path) -> None:
    """Load ``KEY=value`` lines from a ``.env`` file into ``os.environ``.

    Existing environment variables are not overwritten.
    """
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
