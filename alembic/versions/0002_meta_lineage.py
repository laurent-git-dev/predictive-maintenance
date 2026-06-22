"""Lineage schema: meta.processing_runs (batch traceability).

Revision ID: 0002_meta
Revises: 0001_bronze
Create Date: 2026-06-22
"""

from __future__ import annotations

from alembic import op
from src.lineage.models import LineageBase

revision = "0002_meta"
down_revision = "0001_bronze"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS meta")
    LineageBase.metadata.create_all(op.get_bind())


def downgrade() -> None:
    LineageBase.metadata.drop_all(op.get_bind())
    op.execute("DROP SCHEMA IF EXISTS meta CASCADE")
