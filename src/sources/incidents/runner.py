"""Incidents source — bronze/silver builders for the medallion orchestrator.

- Bronze : raw typed data + operator pseudonymisation (privacy gate).
- Silver : feature engineering (datetime, comment_pii_flag, confidence index) +
  declared processing (encode shift, impute severity).
"""

from __future__ import annotations

import logging
import os

from src import config
from src.common.env import load_dotenv
from src.processing.anonymization import pseudonymise_operators
from src.processing.pipeline import ProcessingConfig, apply_processing
from src.sources.incidents import overview
from src.sources.incidents.loader import load_incidents
from src.sources.incidents.pipeline import engineer_silver

logger = logging.getLogger(__name__)

SOURCE_NAME = "incidents"
TABLE = "incidents"
BRONZE_NUMERIC = []
SILVER_NUMERIC = [config.N_SIGNALS_COLUMN, config.CONFIDENCE_COLUMN]
# Features rendered as an incident-count bar chart (severity is ordinal: kept as a
# count chart only, no boxplot/distribution).
COUNT_FEATURES = [
    config.OPERATOR_NAME_COLUMN,
    config.OPERATOR_BADGE_COLUMN,
    config.MACHINE_COLUMN,
    config.SEVERITY_COLUMN,
    config.COMMENT_COLUMN,
    config.SHIFT_COLUMN,
]
COUNT_LABEL = "incidents"
# Keyword bars (feature, keywords, title): isolate a sub-population in free text.
# Here, comments that also flag a production stop (line stop / emergency cut-off).
KEYWORD_BARS = [
    (
        config.COMMENT_COLUMN,
        list(config.PRODUCTION_STOP_MARKERS),
        "Incidents triggering a production stop",
    )
]
# Row-normalised crosstab heatmaps (row × col): does a comment map to a stable severity?
HEATMAPS = [(config.COMMENT_COLUMN, config.SEVERITY_COLUMN)]
# Whole-source overview (chronogram + incidents by signal).
OVERVIEW = overview.plots

PROCESSING = ProcessingConfig(
    encode={config.SHIFT_COLUMN: {"matin": 0, "apres-midi": 1, "nuit": 2}},
    impute={config.SEVERITY_COLUMN: "median"},
    outliers=[],
)


def _salt_and_length() -> tuple[str, int]:
    load_dotenv(config.PROJECT_ROOT / ".env")
    salt = os.environ.get(config.SALT_ENV_VAR, "")
    length = int(os.environ.get(config.PSEUDONYM_LENGTH_ENV_VAR, config.DEFAULT_PSEUDONYM_LENGTH))
    return salt, length


def load_bronze(input_path=None):
    """Raw incidents, with operator_name/operator_badge pseudonymised."""
    salt, length = _salt_and_length()
    df = load_incidents(input_path or config.DEFAULT_INPUT_CSV)
    return pseudonymise_operators(df, salt, length)


def to_silver(bronze_df):
    """Feature engineering + declared processing on the bronze DataFrame."""
    df = engineer_silver(bronze_df)
    df, _ = apply_processing(df, PROCESSING)
    return df
