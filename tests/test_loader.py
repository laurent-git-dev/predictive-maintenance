"""COPY loader correctness — round-trips a mixed frame through PostgreSQL.

Needs a live database (skipped otherwise, e.g. in CI). Verifies the COPY path preserves
values and, critically, distinguishes NULL (NaN/None) from an empty string ("").
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from src.framework.db.engine import get_engine, is_available
from src.framework.db.loader import write_table

pytestmark = pytest.mark.skipif(not is_available(), reason="PostgreSQL not available")

_SCHEMA = "bench_test"


def test_copy_roundtrip_preserves_values_and_nulls():
    engine = get_engine()
    df = pd.DataFrame(
        {
            "i": [1, 2, 3],
            "f": [1.5, np.nan, 3.5],  # NaN -> NULL
            "s": ["a", "", None],  # "" preserved, None -> NULL
            "b": [True, False, True],
        }
    )
    try:
        write_table(df, "roundtrip", engine, _SCHEMA)
        back = pd.read_sql_table("roundtrip", engine, schema=_SCHEMA)

        assert len(back) == 3
        assert back["i"].tolist() == [1, 2, 3]
        assert back["b"].tolist() == [True, False, True]
        assert back["f"].iloc[0] == 1.5
        assert pd.isna(back["f"].iloc[1])  # NaN -> NULL -> NaN
        assert back["s"].iloc[0] == "a"
        assert back["s"].iloc[1] == ""  # empty string kept distinct from NULL
        assert pd.isna(back["s"].iloc[2])  # None -> NULL
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE"))
