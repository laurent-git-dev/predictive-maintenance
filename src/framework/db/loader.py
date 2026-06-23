"""Write processed DataFrames into PostgreSQL tables (per medallion schema).

Bulk-loads via PostgreSQL ``COPY`` (a pandas ``to_sql`` ``method``), which is markedly faster
than the default row-by-row INSERT for wide tables — e.g. the Gold table (≈216 cols × 134k
rows) drops from minutes to under a minute. ``to_sql`` still creates the table from the frame
dtypes; only the data load is replaced.
"""

from __future__ import annotations

import csv
import logging
from io import StringIO

import pandas as pd
from sqlalchemy.engine import Engine

from src.framework.db.engine import ensure_schema

logger = logging.getLogger(__name__)

_NULL = "\\N"  # COPY null marker — distinguishes a real NULL from an empty string ("")


def _copy_into(table, conn, keys, data_iter) -> None:
    """pandas ``to_sql`` method: bulk-load rows via ``COPY`` (NaN/None → NULL, ``""`` kept)."""
    dbapi_conn = conn.connection
    columns = ", ".join(f'"{k}"' for k in keys)
    qualified = f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'

    buffer = StringIO()
    writer = csv.writer(buffer)
    for row in data_iter:
        writer.writerow([_NULL if pd.isna(value) else value for value in row])
    buffer.seek(0)

    with dbapi_conn.cursor() as cur:
        cur.copy_expert(
            f"COPY {qualified} ({columns}) FROM STDIN WITH (FORMAT CSV, NULL '{_NULL}')", buffer
        )


def write_table(
    df: pd.DataFrame, table: str, engine: Engine, schema: str, if_exists: str = "replace"
) -> int:
    """Write a DataFrame to ``<schema>.<table>`` (full reload by default) via COPY.

    The schema is created if needed. Returns the number of rows written.
    """
    ensure_schema(engine, schema)
    df.to_sql(table, engine, schema=schema, if_exists=if_exists, index=False, method=_copy_into)
    logger.info("Loaded %d rows into table '%s.%s'", len(df), schema, table)
    return len(df)
