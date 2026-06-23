"""BatchTracker: record one row per processing step in ``meta.processing_runs``.

Usage::

    batch = Batch(engine)
    with batch.step("ingest", layer="bronze", source="incidents",
                    input_ref="incidents.csv", output_ref="bronze.incidents") as step:
        ...  # do the processing
        step.set(rows_read=n, rows_ingested=m, rows_rejected=k, output_df=df)

The step records start/end timestamps, the status (``success`` / ``failed`` on exception),
the row stats, the current git sha and a content fingerprint of the output. Grouping on
``batch_id`` reconstructs the full lineage of one pipeline execution.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from datetime import datetime
from typing import Literal

import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src import config
from src.framework.lineage.models import LineageBase, ProcessingRun

logger = logging.getLogger(__name__)


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=config.PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:  # noqa: BLE001 - traceability is best-effort
        return None


def _hash_df(df: pd.DataFrame) -> str:
    """Stable 16-char content fingerprint of a DataFrame (order-sensitive, index-free)."""
    digest = pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes()
    return hashlib.sha256(digest).hexdigest()[:16]


def ensure_meta_tables(engine: Engine) -> None:
    """Create the meta schema + lineage table if missing (idempotent; Alembic is the source)."""
    from src.framework.db.engine import ensure_schema

    ensure_schema(engine, config.META_SCHEMA)
    LineageBase.metadata.create_all(engine)


class Batch:
    """One pipeline execution; spawns tracked steps sharing a ``batch_id``."""

    def __init__(self, engine: Engine | None, batch_id: str | None = None):
        self.engine = engine
        self.batch_id = batch_id or datetime.now().strftime("%Y%m%d%H%M%S")
        self.code_version = _git_sha()
        if engine is not None:
            ensure_meta_tables(engine)

    def step(
        self, step: str, *, layer: str, input_ref: str, output_ref: str, source: str | None = None
    ):
        return _Step(self, step, layer, source, input_ref, output_ref)


class _Step:
    def __init__(self, batch: Batch, step, layer, source, input_ref, output_ref):
        self.batch = batch
        self.step = step
        self.layer = layer
        self.source = source
        self.input_ref = input_ref
        self.output_ref = output_ref
        self._s: dict = {}

    def __enter__(self) -> _Step:
        self.started = datetime.now()
        return self

    def set(
        self,
        rows_read=None,
        rows_ingested=None,
        rows_rejected=None,
        quality_ok=None,
        details=None,
        output_df=None,
    ) -> _Step:
        if output_df is not None:
            self._s["output_hash"] = _hash_df(output_df)
            if rows_ingested is None:
                rows_ingested = len(output_df)
        for key, value in dict(
            rows_read=rows_read,
            rows_ingested=rows_ingested,
            rows_rejected=rows_rejected,
            quality_ok=quality_ok,
        ).items():
            if value is not None:
                self._s[key] = value
        if details is not None:
            self._s["details"] = dict(details)
        return self

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        ended = datetime.now()
        status = "failed" if exc_type else "success"
        details = dict(self._s.get("details") or {})
        if exc is not None:
            details["error"] = repr(exc)
        if self.batch.engine is not None:
            self._write(status, ended, details)
        if status == "failed":
            logger.error("Batch %s · %s FAILED: %r", self.batch.batch_id, self.step, exc)
        elif self._s.get("quality_ok") is False:
            logger.warning("Batch %s · %s quality NOK: %s", self.batch.batch_id, self.step, details)
        return False  # never suppress exceptions

    def _write(self, status: str, ended: datetime, details: dict) -> None:
        row = ProcessingRun(
            batch_id=self.batch.batch_id,
            step=self.step,
            layer=self.layer,
            source=self.source,
            input_ref=self.input_ref,
            output_ref=self.output_ref,
            started_at=self.started,
            ended_at=ended,
            duration_s=round((ended - self.started).total_seconds(), 3),
            status=status,
            rows_read=self._s.get("rows_read"),
            rows_ingested=self._s.get("rows_ingested"),
            rows_rejected=self._s.get("rows_rejected"),
            quality_ok=self._s.get("quality_ok"),
            code_version=self.batch.code_version,
            output_hash=self._s.get("output_hash"),
            details=json.dumps(details, default=str) if details else None,
        )
        with Session(self.batch.engine) as session:
            session.add(row)
            session.commit()


def read_runs(engine: Engine, batch_id: str | None = None) -> pd.DataFrame:
    """Read lineage rows (a given batch, or the latest batch if ``batch_id`` is None)."""
    table = f"{config.META_SCHEMA}.processing_runs"
    if batch_id is None:
        from sqlalchemy import text

        with engine.connect() as conn:
            batch_id = conn.execute(
                text(f"SELECT batch_id FROM {table} ORDER BY started_at DESC LIMIT 1")
            ).scalar()
        if batch_id is None:
            return pd.DataFrame()
    return pd.read_sql(
        f"SELECT * FROM {table} WHERE batch_id = '{batch_id}' ORDER BY started_at", engine
    )


def read_all_runs(engine: Engine) -> pd.DataFrame:
    """Read every lineage row across all batches (for the dashboard)."""
    table = f"{config.META_SCHEMA}.processing_runs"
    return pd.read_sql(f"SELECT * FROM {table} ORDER BY started_at", engine)


def lineage_markdown(engine: Engine, batch_id: str | None = None) -> str:
    """Markdown table of a batch's processing steps (the raw->gold lineage)."""
    df = read_runs(engine, batch_id)
    if df.empty:
        return "_No batch recorded yet._"
    cols = [
        "step",
        "layer",
        "source",
        "input_ref",
        "output_ref",
        "status",
        "rows_read",
        "rows_ingested",
        "rows_rejected",
        "quality_ok",
        "duration_s",
    ]
    cols = [c for c in cols if c in df.columns]
    lines = [
        f"**Batch `{df['batch_id'].iloc[0]}`** · code `{df['code_version'].iloc[0]}`",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "---|" * len(cols),
    ]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)
