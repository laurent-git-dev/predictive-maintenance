"""Telemetry source — bronze/silver builders for the medallion orchestrator.

- Bronze : raw typed telemetry (no PII).
- Silver : declared processing (median imputation + IQR outlier clipping).
"""

from __future__ import annotations

import logging

from src import config
from src.processing.pipeline import ProcessingConfig, apply_processing
from src.sources.telemetry.loader import load_telemetry

logger = logging.getLogger(__name__)

SOURCE_NAME = "telemetry"
TABLE = "telemetry"
BRONZE_NUMERIC = list(config.TELEMETRY_PARAM_COLUMNS)
SILVER_NUMERIC = list(config.TELEMETRY_PARAM_COLUMNS)

_PROCESSING = ProcessingConfig(
    encode={},
    impute={param: "median" for param in config.TELEMETRY_PARAM_COLUMNS},
    outliers=list(config.TELEMETRY_PARAM_COLUMNS),
)


def load_bronze(input_path=None):
    """Raw telemetry DataFrame."""
    return load_telemetry(input_path or config.DEFAULT_TELEMETRY_CSV)


def to_silver(bronze_df):
    """Declared processing on the bronze DataFrame."""
    df, _ = apply_processing(bronze_df, _PROCESSING)
    return df
