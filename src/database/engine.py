"""SQLAlchemy engine for the PostgreSQL database (read from the environment)."""

from __future__ import annotations

import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src import config

logger = logging.getLogger(__name__)


def database_url() -> str:
    """Build the PostgreSQL connection URL from environment variables."""
    env = {k: os.environ.get(k, default) for k, default in config.DB_ENV_DEFAULTS.items()}
    return (
        f"postgresql+psycopg2://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/{env['POSTGRES_DB']}"
    )


def get_engine() -> Engine:
    """Create a SQLAlchemy engine with a short connect timeout and pre-ping."""
    return create_engine(
        database_url(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": config.DB_CONNECT_TIMEOUT_SECONDS},
    )


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
