"""ORM model for the lineage table ``meta.processing_runs`` (one row per processing step).

A *batch* (``batch_id``) groups all the steps of one pipeline execution, so filtering on it
reconstructs the full lineage from the DataLake files to ``gold.features``.
"""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src import config

SCHEMA = config.META_SCHEMA


class LineageBase(DeclarativeBase):
    """Declarative base for the lineage table (in the ``meta`` schema)."""


class ProcessingRun(LineageBase):
    __tablename__ = "processing_runs"
    __table_args__ = {"schema": SCHEMA}

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(32), index=True)  # one pipeline execution
    step: Mapped[str] = mapped_column(String(64))  # e.g. ingest / refine / build
    layer: Mapped[str] = mapped_column(String(16))  # bronze | silver | gold | cross_source
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_ref: Mapped[str] = mapped_column(String(256))  # input data identification
    output_ref: Mapped[str] = mapped_column(String(256))  # output data identification
    started_at: Mapped[str] = mapped_column(DateTime)
    ended_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16))  # success | failed | skipped
    rows_read: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_ingested: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_rejected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    code_version: Mapped[str | None] = mapped_column(String(40), nullable=True)  # git short sha
    output_hash: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # content fingerprint
    details: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON (stats / quality / error)
