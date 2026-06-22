"""Generic, source-agnostic data-quality metrics."""

from __future__ import annotations

import logging

import pandas as pd

from src import config

logger = logging.getLogger(__name__)


def compute_quality_metrics(df: pd.DataFrame) -> dict:
    """Compute the quality metrics required for the runs registry.

    Works for any source whose machine column is ``config.MACHINE_COLUMN``.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame to measure.

    Returns
    -------
    dict
        Metrics: ``n_rows``, ``n_columns``, ``unique_machines``,
        ``n_missing_total`` and the ``n_missing_per_column`` breakdown.
    """
    unique_machines = (
        int(df[config.MACHINE_COLUMN].nunique()) if config.MACHINE_COLUMN in df.columns else 0
    )
    missing_per_column = df.isna().sum()

    metrics = {
        "n_rows": int(len(df)),
        "n_columns": int(df.shape[1]),
        "unique_machines": unique_machines,
        "n_missing_total": int(missing_per_column.sum()),
        "n_missing_per_column": {
            col: int(n) for col, n in missing_per_column.items() if int(n) > 0
        },
    }
    logger.info(
        "Quality metrics — rows=%d, columns=%d, machines=%d, missing=%d",
        metrics["n_rows"],
        metrics["n_columns"],
        metrics["unique_machines"],
        metrics["n_missing_total"],
    )
    return metrics
