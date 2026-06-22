"""Time helpers (framework). Reusable, dependency-light datetime utilities."""

from __future__ import annotations

import pandas as pd


def to_naive_hour(series: pd.Series) -> pd.Series:
    """Parse to datetime, drop any timezone, and floor to the hour.

    Tz-aware stamps (e.g. ``maintenance_at`` in UTC) are made naive so all sources share a
    single comparable hourly grid. Unparseable values become ``NaT``.
    """
    t = pd.to_datetime(series, errors="coerce")
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_localize(None)
    return t.dt.floor("h")
