"""Machines/maintenance source — bronze/silver builders for the orchestrator.

- Bronze : maintenance events loaded from the SQL dump (no PII).
- Silver : declared processing (encode type/component, IQR outlier clipping on duration).
"""

from __future__ import annotations

import logging

from src import config
from src.processing.pipeline import ProcessingConfig, apply_processing
from src.sources.machines.loader import build_engine, load_maintenance

logger = logging.getLogger(__name__)

SOURCE_NAME = "machines"
TABLE = "maintenance"
BRONZE_NUMERIC = [config.MAINTENANCE_DURATION_COLUMN]
SILVER_NUMERIC = [config.MAINTENANCE_DURATION_COLUMN]

_PROCESSING = ProcessingConfig(
    encode={config.MAINTENANCE_TYPE_COLUMN: {"proactive": 0, "reactive": 1}, "component": None},
    impute={},
    outliers=[config.MAINTENANCE_DURATION_COLUMN],
)


def load_bronze(input_path=None):
    """Raw maintenance DataFrame (machine_code renamed to machine_id)."""
    engine = build_engine(input_path or config.DEFAULT_MACHINES_SQL)
    return load_maintenance(engine)


def to_silver(bronze_df):
    """Declared processing on the bronze DataFrame."""
    df, _ = apply_processing(bronze_df, _PROCESSING)
    return df
