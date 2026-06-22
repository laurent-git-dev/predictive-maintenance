"""Unit tests for the B3 shared utilities (time floor + markdown table)."""

from __future__ import annotations

import pandas as pd

from src.framework.common.reporting import markdown_table
from src.framework.timeutils import to_naive_hour


def test_to_naive_hour_floors_to_the_hour():
    s = pd.Series(["2025-01-01 09:45:00", "2025-01-01 10:05:00"])
    out = to_naive_hour(s)
    assert list(out) == [
        pd.Timestamp("2025-01-01 09:00:00"),
        pd.Timestamp("2025-01-01 10:00:00"),
    ]


def test_to_naive_hour_drops_timezone():
    s = pd.to_datetime(pd.Series(["2025-01-01 09:45:00"]), utc=True)  # 09:45 UTC
    out = to_naive_hour(s)
    assert out.dt.tz is None
    assert out.iloc[0] == pd.Timestamp("2025-01-01 09:00:00")


def test_to_naive_hour_coerces_bad_values_to_nat():
    out = to_naive_hour(pd.Series(["not-a-date"]))
    assert out.isna().all()


def test_markdown_table_exact_format():
    out = markdown_table(["a", "b"], [[1, 2], ["x", "y"]])
    assert out == "| a | b |\n|---|---|\n| 1 | 2 |\n| x | y |"
