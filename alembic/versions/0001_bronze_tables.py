"""Initial Bronze schema: the 4 raw tables (incidents, telemetry, machine, maintenance).

Revision ID: 0001_bronze
Revises:
Create Date: 2026-06-22
"""

from __future__ import annotations

from alembic import op
from src.usecase.db.models_bronze import BronzeBase

revision = "0001_bronze"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the 4 Bronze tables (the ``bronze`` schema is ensured in env.py)."""
    BronzeBase.metadata.create_all(op.get_bind())


def downgrade() -> None:
    """Drop the 4 Bronze tables."""
    BronzeBase.metadata.drop_all(op.get_bind())
