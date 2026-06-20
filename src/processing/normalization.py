"""Feature normalization / standardization (mutualised, no I/O)."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_METHODS = ("zscore", "minmax")


def normalize(df: pd.DataFrame, methods: dict[str, str]) -> tuple[pd.DataFrame, dict]:
    """Add a ``<col>_norm`` column for each ``column -> method``.

    Parameters
    ----------
    df : pandas.DataFrame
        Input data (a copy is returned; original columns are preserved).
    methods : dict[str, str]
        ``column -> method`` among ``zscore`` (standardisation, mean 0 / std 1) and
        ``minmax`` (scaled to ``[0, 1]``).

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        The enriched frame and a report ``column -> {method, params}``.
    """
    df = df.copy()
    report: dict = {}
    for col, method in methods.items():
        if col not in df.columns or method not in _METHODS:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        new_col = f"{col}_norm"
        if method == "zscore":
            mean, std = float(series.mean()), float(series.std())
            df[new_col] = (series - mean) / std if std else 0.0
            params = {"mean": round(mean, 6), "std": round(std, 6)}
        else:  # minmax
            mn, mx = float(series.min()), float(series.max())
            span = mx - mn
            df[new_col] = (series - mn) / span if span else 0.0
            params = {"min": round(mn, 6), "max": round(mx, 6)}
        report[col] = {"method": method, "params": params}
        logger.info("Normalized '%s' -> '%s' (%s)", col, new_col, method)
    return df, report
