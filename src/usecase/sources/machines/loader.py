"""Load the machines/maintenance SQL dump into SQLite and expose DataFrames.

The dump is a PostgreSQL export. Rather than depend on PostgreSQL, we let the
ORM models create the tables in a local SQLite database, then replay the dump's
``INSERT`` statements. Data is then read back into pandas for EDA.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from src import config
from src.usecase.sources.machines.models import Base

logger = logging.getLogger(__name__)


def _extract_insert_statements(sql_path: Path) -> list[str]:
    """Return the ``INSERT`` statements from the dump (DDL is skipped).

    The PostgreSQL ``ON CONFLICT ... DO UPDATE`` upsert clause is dropped: it is
    unnecessary on a fresh database and uses PG-only syntax (``NOW()``).
    """
    sql = Path(sql_path).read_text(encoding="utf-8")
    statements = []
    for raw in sql.split(";"):
        stmt = raw.strip()
        if not stmt.upper().startswith("INSERT"):
            continue
        idx = stmt.upper().find("ON CONFLICT")
        if idx != -1:
            stmt = stmt[:idx].rstrip()
        statements.append(stmt)
    return statements


def build_engine(sql_path: str | Path = config.DEFAULT_MACHINES_SQL) -> Engine:
    """Create an in-memory SQLite database, then load the dump's data.

    Tables are created from the ORM models (portable schema); the dump's
    ``INSERT`` statements are replayed to populate them.

    Raises
    ------
    FileNotFoundError
        If the SQL file does not exist.
    """
    sql_path = Path(sql_path)
    if not sql_path.exists():
        raise FileNotFoundError(
            f"SQL file not found: {sql_path}. Drop the dump into data/raw/ (see CLAUDE.md)."
        )

    logger.info("Building SQLite database from: %s", sql_path)
    # StaticPool keeps a single shared in-memory connection across the engine.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)

    statements = _extract_insert_statements(sql_path)
    with engine.begin() as conn:
        for stmt in statements:
            conn.exec_driver_sql(stmt)
    logger.info("Loaded %d INSERT statements into SQLite.", len(statements))
    return engine


def load_maintenance(engine: Engine) -> pd.DataFrame:
    """Read the maintenance table into a typed DataFrame.

    ``machine_code`` is renamed to ``machine_id`` for consistency with the other
    sources (and future cross-source joins).
    """
    df = pd.read_sql("SELECT * FROM maintenance", engine)
    df = df.rename(columns={"machine_code": config.MACHINE_COLUMN})
    df[config.MAINTENANCE_TIMESTAMP_COLUMN] = pd.to_datetime(
        df[config.MAINTENANCE_TIMESTAMP_COLUMN], errors="coerce", utc=True
    )
    df[config.MAINTENANCE_DURATION_COLUMN] = pd.to_numeric(
        df[config.MAINTENANCE_DURATION_COLUMN], errors="coerce"
    )
    return df


def load_machine_referential(engine: Engine) -> pd.DataFrame:
    """Read the machine referential into a DataFrame (``machine_code`` -> ``machine_id``)."""
    df = pd.read_sql("SELECT * FROM machine", engine)
    df = df.rename(columns={"machine_code": config.MACHINE_COLUMN})
    df["commissioning_date"] = pd.to_datetime(df["commissioning_date"], errors="coerce")
    return df
