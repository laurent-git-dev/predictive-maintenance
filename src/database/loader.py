"""Write processed DataFrames into PostgreSQL tables (per medallion schema)."""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.engine import Engine

from src.database.engine import ensure_schema

logger = logging.getLogger(__name__)


def write_table(
    df: pd.DataFrame, table: str, engine: Engine, schema: str, if_exists: str = "replace"
) -> int:
    """Write a DataFrame to ``<schema>.<table>`` (full reload by default).

    The schema is created if needed. Returns the number of rows written.
    """
    ensure_schema(engine, schema)
    df.to_sql(table, engine, schema=schema, if_exists=if_exists, index=False)
    logger.info("Loaded %d rows into table '%s.%s'", len(df), schema, table)
    return len(df)
