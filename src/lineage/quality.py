"""Soft data-quality checks recorded per processing step (no hard failure).

Returns ``(quality_ok, details)``: duplicate check on the declared grain and row-count
continuity vs the previous batch for the same output (to spot erratic regenerations).
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src import config

_JUMP = 0.2  # relative row-count change vs the previous batch that triggers a warning


def _previous_rows(output_ref: str, engine: Engine, batch_id: str) -> int | None:
    """Most recent ``rows_ingested`` recorded for ``output_ref`` in an earlier batch."""
    q = text(
        f"SELECT rows_ingested FROM {config.META_SCHEMA}.processing_runs "
        "WHERE output_ref = :o AND batch_id <> :b AND rows_ingested IS NOT NULL "
        "ORDER BY started_at DESC LIMIT 1"
    )
    try:
        with engine.connect() as conn:
            value = conn.execute(q, {"o": output_ref, "b": batch_id}).scalar()
        return int(value) if value is not None else None
    except Exception:  # noqa: BLE001 - quality is best-effort, never breaks the pipeline
        return None


def check_quality(
    output_ref: str,
    df: pd.DataFrame,
    engine: Engine | None,
    batch_id: str,
    grain: list[str] | None = None,
) -> tuple[bool, dict]:
    """Compute the soft quality verdict + details for a step's output."""
    details: dict = {}
    ok = True
    if grain:
        present = [c for c in grain if c in df.columns]
        dups = int(df.duplicated(present).sum()) if present else 0
        details["grain_duplicates"] = dups
        ok = ok and dups == 0
    if engine is not None:
        prev = _previous_rows(output_ref, engine, batch_id)
        if prev:
            details["prev_rows"] = prev
            details["row_delta"] = len(df) - prev
            if abs(len(df) - prev) / prev > _JUMP:
                ok = False
                details["row_count_jump"] = True
    return ok, details
