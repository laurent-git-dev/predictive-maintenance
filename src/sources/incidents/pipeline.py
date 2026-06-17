"""Incidents feature engineering (Silver): derived columns from the Bronze data."""

from __future__ import annotations

import logging

import pandas as pd

from src import config

logger = logging.getLogger(__name__)


def add_confidence_index(df: pd.DataFrame) -> pd.DataFrame:
    """Add the number of active signals and the confidence index per incident.

    The confidence index is ``n_active_signals / total_signals``: an incident
    corroborated by several simultaneous signals is deemed more reliable than
    one relying on a single isolated signal.
    """
    df = df.copy()
    present_signals = [c for c in config.SIGNAL_COLUMNS if c in df.columns]
    if not present_signals:
        logger.warning("No signal column found: confidence index skipped.")
        return df

    signals = df[present_signals].fillna(0).astype(int)
    df[config.N_SIGNALS_COLUMN] = signals.sum(axis=1)
    df[config.CONFIDENCE_COLUMN] = (df[config.N_SIGNALS_COLUMN] / len(present_signals)).round(4)
    return df


def engineer_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Silver feature engineering for incidents (operators already pseudonymised).

    Adds:
    - ``datetime`` : combined date + time (fine-grained temporal analysis) ;
    - ``comment_pii_flag`` : whether the free ``comment`` holds text (PII review) ;
    - ``n_active_signals`` / ``confidence_index`` (see :func:`add_confidence_index`).
    """
    df = df.copy()

    if config.DATE_COLUMN in df.columns and config.TIME_COLUMN in df.columns:
        combined = (
            df[config.DATE_COLUMN].dt.strftime(config.DATE_FORMAT)
            + " "
            + df[config.TIME_COLUMN].astype(str)
        )
        df[config.DATETIME_COLUMN] = pd.to_datetime(combined, errors="coerce")

    if config.COMMENT_COLUMN in df.columns:
        df["comment_pii_flag"] = df[config.COMMENT_COLUMN].notna() & df[
            config.COMMENT_COLUMN
        ].astype(str).str.strip().ne("")

    return add_confidence_index(df)
