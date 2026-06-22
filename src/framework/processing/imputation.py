"""Imputation of missing values (mutualised, no I/O)."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_STRATEGIES = ("median", "mean", "mode")


def impute(df: pd.DataFrame, strategies: dict[str, str]) -> tuple[pd.DataFrame, dict]:
    """Fill missing values column by column.

    Parameters
    ----------
    df : pandas.DataFrame
        Input data (a copy is returned).
    strategies : dict[str, str]
        ``column -> strategy`` among ``median``, ``mean``, ``mode``.

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        The imputed DataFrame and a report ``column -> {strategy, n_filled}``.
    """
    df = df.copy()
    report: dict = {}
    for col, strategy in strategies.items():
        if col not in df.columns or strategy not in _STRATEGIES:
            continue
        n_missing = int(df[col].isna().sum())
        if n_missing == 0:
            continue
        if strategy == "median":
            fill = pd.to_numeric(df[col], errors="coerce").median()
        elif strategy == "mean":
            fill = pd.to_numeric(df[col], errors="coerce").mean()
        else:  # mode
            modes = df[col].mode(dropna=True)
            fill = modes.iloc[0] if not modes.empty else None
        if fill is None:
            continue
        df[col] = df[col].fillna(fill)
        report[col] = {"strategy": strategy, "n_filled": n_missing}
        logger.info("Imputed %d missing in '%s' (%s)", n_missing, col, strategy)
    return df, report
