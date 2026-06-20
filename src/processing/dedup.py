"""Row deduplication on key columns (mutualised, no I/O)."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_STRATEGIES = ("mean", "first", "last")


def deduplicate(
    df: pd.DataFrame, keys: list[str], strategy: str = "first"
) -> tuple[pd.DataFrame, dict]:
    """Collapse rows that share the same ``keys``.

    Parameters
    ----------
    df : pandas.DataFrame
        Input data (a new frame is returned).
    keys : list[str]
        Columns identifying a logical record.
    strategy : str
        ``first`` / ``last`` keep that row of each duplicate group; ``mean`` averages
        the numeric columns within each group (first value for non-numeric columns),
        reconciling conflicting readings.

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        The deduplicated frame and a report ``{keys, strategy, n_removed}``.
    """
    present = [k for k in keys if k in df.columns]
    if not present or strategy not in _STRATEGIES:
        return df, {}

    n_before = len(df)
    if strategy in ("first", "last"):
        out = df.drop_duplicates(subset=present, keep=strategy)
    else:  # mean: reconcile conflicting duplicates
        num_cols = [
            c for c in df.columns if c not in present and pd.api.types.is_numeric_dtype(df[c])
        ]
        other_cols = [c for c in df.columns if c not in present and c not in num_cols]
        agg = {**{c: "mean" for c in num_cols}, **{c: "first" for c in other_cols}}
        out = df.groupby(present, as_index=False, sort=False).agg(agg)
        out = out[[c for c in df.columns if c in out.columns]]  # restore column order

    out = out.reset_index(drop=True)
    n_removed = n_before - len(out)
    report = {"keys": present, "strategy": strategy, "n_removed": int(n_removed)}
    if n_removed:
        logger.info("Deduplicated on %s (%s): removed %d rows", present, strategy, n_removed)
    return out, report
