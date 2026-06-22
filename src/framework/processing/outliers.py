"""Outlier detection and treatment (mutualised, no I/O)."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def treat_outliers(
    df: pd.DataFrame, columns: list[str], k: float = 1.5
) -> tuple[pd.DataFrame, dict]:
    """Detect outliers with the IQR rule and clip (winsorize) them.

    For each column, values outside ``[Q1 - k*IQR, Q3 + k*IQR]`` are clipped to the
    bounds (non-destructive: row count is preserved).

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        The treated DataFrame and a report ``column -> {n_clipped, low, high}``.
    """
    df = df.copy()
    report: dict = {}
    for col in columns:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        low, high = q1 - k * iqr, q3 + k * iqr
        n_clipped = int(((series < low) | (series > high)).sum())
        df[col] = series.clip(low, high)
        report[col] = {
            "n_clipped": n_clipped,
            "low": round(float(low), 3),
            "high": round(float(high), 3),
        }
        logger.info("Clipped %d outliers in '%s' to [%.3f, %.3f]", n_clipped, col, low, high)
    return df, report
