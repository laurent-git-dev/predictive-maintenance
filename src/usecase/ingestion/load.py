"""Bronze ingestion: validate/flag a raw DataFrame, then load it into its Bronze table.

All rows are ingested (none dropped/modified) with the ``parse_ok`` / ``parse_reason`` flags.
The Bronze schema/tables are managed by Alembic; ``ensure_bronze_tables`` is an idempotent
runtime safety net so the notebook/pipeline also work before an explicit ``alembic upgrade``.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.framework.db.engine import ensure_schema
from src.framework.ingestion.validate import validate_and_flag
from src.usecase.db.models_bronze import SCHEMA, BronzeBase
from src.usecase.sources.registry import SPECS_BY_NAME

logger = logging.getLogger(__name__)


def ensure_bronze_tables(engine: Engine) -> None:
    """Create the Bronze schema + tables if missing (idempotent; Alembic is the source of truth)."""
    ensure_schema(engine, SCHEMA)
    BronzeBase.metadata.create_all(engine)


def ingest_bronze(name: str, raw_df: pd.DataFrame, engine: Engine | None = None) -> tuple:
    """Validate/flag ``raw_df`` then load into ``bronze.<table>``; returns ``(flagged, status)``."""
    spec = SPECS_BY_NAME[name]
    assert spec.model is not None, f"source '{name}' has no Pydantic MODEL declared"
    flagged = validate_and_flag(raw_df, spec.model, spec.dup_keys)
    table = spec.table

    if engine is not None:
        ensure_bronze_tables(engine)
        with engine.begin() as conn:
            conn.execute(text(f'TRUNCATE TABLE {SCHEMA}."{table}" RESTART IDENTITY'))
        flagged.to_sql(table, engine, schema=SCHEMA, if_exists="append", index=False)
        db = f"{len(flagged)} rows -> {SCHEMA}.{table}"
    else:
        db = "skipped (PostgreSQL unavailable)"

    status = {
        "rows": len(flagged),
        "parse_ok": int(flagged["parse_ok"].sum()),
        "parse_ko": int((~flagged["parse_ok"]).sum()),
        "db": db,
    }
    logger.info("Ingested %s: %s", name, db)
    return flagged, status
