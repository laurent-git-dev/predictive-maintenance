"""Loading and validation of the incidents CSV file.

The loader is intentionally lenient: it reports schema deviations (via
``logging``) without aborting the run, so it stays usable on real exports that
are sometimes imperfect.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src import config

logger = logging.getLogger(__name__)


def load_incidents(path: str | Path) -> pd.DataFrame:
    """Load the incidents CSV and apply basic typing.

    Parameters
    ----------
    path : str | Path
        Path to the source CSV file.

    Returns
    -------
    pandas.DataFrame
        Typed DataFrame: dates as ``datetime``, signals as nullable integers,
        and a computed ``datetime`` column (date + time) when possible.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Source file not found: {path}. Drop the CSV into data/raw/ (see CLAUDE.md)."
        )

    logger.info("Reading CSV: %s", path)
    df = pd.read_csv(path, sep=config.CSV_SEPARATOR, encoding=config.CSV_ENCODING)
    logger.info("CSV loaded: %d rows, %d columns", len(df), df.shape[1])

    _validate_schema(df)
    df = _coerce_types(df)
    return df


def _validate_schema(df: pd.DataFrame) -> None:
    """Compare the present columns to the expected schema and log deviations."""
    present = set(df.columns)
    expected = set(config.EXPECTED_COLUMNS)

    missing = expected - present
    extra = present - expected
    if missing:
        logger.warning("Expected columns missing: %s", sorted(missing))
    if extra:
        logger.warning("Unexpected columns (kept): %s", sorted(extra))
    if not missing and not extra:
        logger.info("Schema matches CLAUDE.md.")


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Bronze-level typing only: dates and integer signals.

    The combined ``datetime`` column is feature engineering and lives in Silver.
    """
    df = df.copy()

    # Date as ISO 8601.
    if config.DATE_COLUMN in df.columns:
        df[config.DATE_COLUMN] = pd.to_datetime(
            df[config.DATE_COLUMN], format=config.DATE_FORMAT, errors="coerce"
        )

    # Signals: nullable integers (0/1). Also handles boolean values.
    for col in config.SIGNAL_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round().astype("Int64")

    return df
