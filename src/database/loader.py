"""Write processed DataFrames into PostgreSQL tables."""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def write_table(df: pd.DataFrame, table: str, engine: Engine, if_exists: str = "replace") -> int:
    """Write a DataFrame to a SQL table (full reload by default).

    Parameters
    ----------
    df : pandas.DataFrame
        Data to load.
    table : str
        Target table name.
    engine : sqlalchemy.engine.Engine
        Database engine.
    if_exists : str, optional
        ``replace`` (default, idempotent reload), ``append`` or ``fail``.

    Returns
    -------
    int
        Number of rows written.
    """
    df.to_sql(table, engine, if_exists=if_exists, index=False)
    logger.info("Loaded %d rows into table '%s'", len(df), table)
    return len(df)
