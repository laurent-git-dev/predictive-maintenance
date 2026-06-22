"""Time-series interpolation per group (mutualised, no I/O).

Fill missing values by interpolating each target column **within its group** (e.g. one
machine), ordered by time. Faithful to a per-entity time series — unlike a global
statistic (mean/median), which collapses all gaps onto a single value and injects an
artificial spike at that value.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def interpolate_by_group(
    df: pd.DataFrame,
    group_col: str,
    time_col: str,
    columns: list[str],
    method: str = "time",
) -> tuple[pd.DataFrame, dict]:
    """Interpolate missing values within each ``group_col``, ordered by ``time_col``.

    Parameters
    ----------
    df : pandas.DataFrame
        Input data (a copy is returned; row order is preserved).
    group_col, time_col : str
        Grouping key (e.g. ``machine_id``) and ordering timestamp.
    columns : list[str]
        Numeric columns to fill.
    method : str
        Interpolation method passed to :meth:`pandas.Series.interpolate`
        (``"time"`` = linear with respect to the timestamps). Any leading/trailing gap
        is then closed by forward/backward fill.

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        The filled frame and a report ``column -> {method, n_filled}``.
    """
    df = df.copy()
    present = [c for c in columns if c in df.columns]
    report: dict = {}
    if not present or group_col not in df.columns or time_col not in df.columns:
        return df, report

    groups = df.assign(__t=pd.to_datetime(df[time_col], errors="coerce")).groupby(
        group_col, sort=False
    )
    for col in present:
        before = int(pd.to_numeric(df[col], errors="coerce").isna().sum())
        parts = []
        for _, grp in groups:
            series = pd.to_numeric(grp[col], errors="coerce")
            series.index = pd.DatetimeIndex(grp["__t"].to_numpy())
            series = series.interpolate(method=method, limit_direction="both").ffill().bfill()
            parts.append(pd.Series(series.to_numpy(), index=grp.index))
        df[col] = pd.concat(parts).reindex(df.index)
        after = int(pd.to_numeric(df[col], errors="coerce").isna().sum())
        report[col] = {"method": method, "n_filled": before - after}
        logger.info(
            "Interpolated %d missing in '%s' (%s, per %s)", before - after, col, method, group_col
        )
    return df, report
