"""Alembic environment for the Bronze schema (connection & metadata from the project)."""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

# Make the project importable (src) when Alembic runs from the project root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.common.env import load_dotenv  # noqa: E402
from src.database.engine import database_url  # noqa: E402
from src.database.models_bronze import SCHEMA, BronzeBase  # noqa: E402

cfg = context.config
if cfg.config_file_name is not None:
    fileConfig(cfg.config_file_name)

load_dotenv(ROOT / ".env")
cfg.set_main_option("sqlalchemy.url", database_url())
target_metadata = BronzeBase.metadata


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=cfg.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table_schema=SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config, pool
    from sqlalchemy.schema import CreateSchema

    connectable = engine_from_config(
        cfg.get_section(cfg.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        if not connection.dialect.has_schema(connection, SCHEMA):
            connection.execute(CreateSchema(SCHEMA))
            connection.commit()
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
