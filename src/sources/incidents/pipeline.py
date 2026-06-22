"""Incidents feature engineering (Gold): derived columns from the Silver data."""

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


def engineer_gold(df: pd.DataFrame) -> pd.DataFrame:
    """Gold feature engineering for incidents (from the treated Silver data).

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
        dt = df[config.DATETIME_COLUMN].dt
        df["hour"] = dt.hour.astype("Int64")
        df["weekday"] = dt.weekday.astype("Int64")
        df["month"] = dt.month.astype("Int64")
        df["is_weekend"] = (dt.weekday >= 5).astype("Int64")

    if config.COMMENT_COLUMN in df.columns:
        comment = df[config.COMMENT_COLUMN]
        df["comment_pii_flag"] = comment.notna() & comment.astype(str).str.strip().ne("")
        lowered = comment.fillna("").astype(str).str.lower()
        markers = [m.lower() for m in config.PRODUCTION_STOP_MARKERS]
        df["production_stop_flag"] = lowered.apply(
            lambda text: any(marker in text for marker in markers)
        ).astype("Int64")

    return add_confidence_index(df)
