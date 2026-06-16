"""Generic runs-registry helper, shared by all sources."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def upsert_run(registry_path: Path, entry: dict) -> None:
    """Insert or replace a run entry (keyed by ``run_id``) in a JSON registry.

    Parameters
    ----------
    registry_path : pathlib.Path
        Path to the source's ``runs_registry.json``.
    entry : dict
        Run entry; must contain a ``run_id`` key.
    """
    registry: dict = {"runs": []}
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Unreadable registry, resetting.")

    registry.setdefault("runs", [])
    registry["runs"] = [r for r in registry["runs"] if r.get("run_id") != entry["run_id"]]
    registry["runs"].append(entry)
    registry["runs"].sort(key=lambda r: r["run_id"])

    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Registry updated: %s (%d runs)", registry_path.name, len(registry["runs"]))
