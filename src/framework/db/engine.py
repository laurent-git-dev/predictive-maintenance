"""SQLAlchemy engine for the PostgreSQL database (read from the environment)."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src import config
from src.settings import get_settings

logger = logging.getLogger(__name__)


def database_url() -> str:
    """Build the PostgreSQL connection URL from the centralised settings."""
    return get_settings().database_url


def get_engine() -> Engine:
    """Create a SQLAlchemy engine with a short connect timeout and pre-ping."""
    return create_engine(
        database_url(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": config.DB_CONNECT_TIMEOUT_SECONDS},
    )


def ensure_schema(engine: Engine, schema: str) -> None:
    """Create the schema if it does not exist (idempotent)."""
    from sqlalchemy.schema import CreateSchema

    with engine.begin() as conn:
        conn.execute(CreateSchema(schema, if_not_exists=True))


def is_available() -> bool:
    """Return ``True`` if PostgreSQL is reachable; never raises (logs a warning)."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - we deliberately degrade gracefully
        logger.warning("PostgreSQL not available (DB load will be skipped): %s", exc)
        return False
