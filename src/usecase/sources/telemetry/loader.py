"""Loading and validation of the machine telemetry CSV file.

Telemetry has no PII, so there is no anonymisation step. Quality metrics reuse
the generic helper from the ingestion package.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src import config

logger = logging.getLogger(__name__)


def load_telemetry(path: str | Path) -> pd.DataFrame:
    """Load the telemetry CSV and apply basic typing.

    Parameters
    ----------
    path : str | Path
        Path to the source CSV file.

    Returns
    -------
    pandas.DataFrame
        Typed DataFrame: ``timestamp`` parsed to datetime, parameters coerced to
        numeric.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Telemetry file not found: {path}. Drop the CSV into data/raw/ (see CLAUDE.md)."
        )

    logger.info("Reading telemetry CSV: %s", path)
    df = pd.read_csv(path, sep=config.CSV_SEPARATOR, encoding=config.CSV_ENCODING)
    logger.info("Telemetry loaded: %d rows, %d columns", len(df), df.shape[1])

    _validate_schema(df)
    df = _coerce_types(df)
    return df


def _validate_schema(df: pd.DataFrame) -> None:
    """Compare present columns to the expected telemetry schema and log deviations."""
    present = set(df.columns)
    expected = set(config.TELEMETRY_EXPECTED_COLUMNS)

    missing = expected - present
    extra = present - expected
    if missing:
        logger.warning("Expected columns missing: %s", sorted(missing))
    if extra:
        logger.warning("Unexpected columns (kept): %s", sorted(extra))
    if not missing and not extra:
        logger.info("Telemetry schema matches CLAUDE.md.")


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Apply typing: timestamp to datetime, parameters to numeric."""
    df = df.copy()

    if config.TELEMETRY_TIMESTAMP_COLUMN in df.columns:
        df[config.TELEMETRY_TIMESTAMP_COLUMN] = pd.to_datetime(
            df[config.TELEMETRY_TIMESTAMP_COLUMN], errors="coerce"
        )

    for col in config.TELEMETRY_PARAM_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df
