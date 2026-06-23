"""Incidents source — bronze/silver/gold builders for the medallion orchestrator.

- Bronze : raw typed data + operator pseudonymisation (privacy gate).
- Silver : treatment only (encode shift, impute severity) — no feature engineering.
- Gold   : handled by the unified builder (src/gold/features.py); incident events are
  enriched (engineer_gold) and aggregated to the (machine, hour) grain there.
"""

from __future__ import annotations

import logging

from src import config
from src.framework.processing.anonymization import pseudonymise_operators
from src.framework.processing.pipeline import ProcessingConfig, apply_processing
from src.settings import get_settings
from src.usecase.ingestion.schemas import IncidentRow
from src.usecase.sources.incidents import overview
from src.usecase.sources.incidents.loader import load_incidents

logger = logging.getLogger(__name__)

SOURCE_NAME = "incidents"
TABLE = "incidents"
MODEL = IncidentRow  # Bronze validation/flagging schema
DUP_KEYS = [config.ID_COLUMN]  # duplicate detection key
RAW_REF = "incidents.csv"  # DataLake input (lineage)
GOLD_ROLE = "incidents"  # feeds the unified Gold builder's incidents slot
BRONZE_NUMERIC: list[str] = []
SILVER_NUMERIC: list[str] = []  # severity is ordinal (count only); no continuous numeric in Silver
# Features rendered as an incident-count bar chart (severity is ordinal: kept as a count
# chart only). Calendar/flag features live in the unified Gold table (built per (machine, hour)).
COUNT_FEATURES = [
    config.OPERATOR_NAME_COLUMN,
    config.OPERATOR_BADGE_COLUMN,
    config.MACHINE_COLUMN,
    config.SEVERITY_COLUMN,
    config.COMMENT_COLUMN,
    config.SHIFT_COLUMN,
    "hour",
    "weekday",
    "month",
    # Silver-only 0/1 flags: a count bar (0 vs 1) visualises the engineered features.
    "is_weekend",
    "comment_pii_flag",
    "production_stop_flag",
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
    settings = get_settings()
    return settings.anonymization_salt, settings.pseudonym_length


def load_bronze(input_path=None):
    """Raw incidents, with operator_name/operator_badge pseudonymised."""
    salt, length = _salt_and_length()
    df = load_incidents(input_path or config.DEFAULT_INPUT_CSV)
    return pseudonymise_operators(df, salt, length)


def to_silver(bronze_df):
    """Treatment only (encode shift, impute severity); returns ``(silver_df, report)``."""
    return apply_processing(bronze_df, PROCESSING)


# Feature engineering (``engineer_gold``) is applied at incident-event level by the unified
# Gold builder (``src/gold/features.py``) before aggregation to the (machine, hour) grain.
