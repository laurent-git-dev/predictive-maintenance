"""Machines/maintenance source — bronze/silver builders for the orchestrator.

- Bronze : maintenance events loaded from the SQL dump (no PII).
- Silver : declared processing (encode type/component, IQR outlier clipping on duration)
  + enrichment with the machine dimension attributes (criticality, line, location, ...).
"""

from __future__ import annotations

import logging

from src import config
from src.processing.pipeline import ProcessingConfig, apply_processing
from src.sources.machines import overview
from src.sources.machines.loader import build_engine, load_machine_referential, load_maintenance

logger = logging.getLogger(__name__)

SOURCE_NAME = "machines"
TABLE = "maintenance"
BRONZE_NUMERIC = [config.MAINTENANCE_DURATION_COLUMN]
SILVER_NUMERIC = [config.MAINTENANCE_DURATION_COLUMN]
# Maintenance count per category (descending; horizontal bars beyond 20 modalities).
COUNT_FEATURES = [config.MAINTENANCE_COMPONENT_COLUMN, config.MAINTENANCE_DESCRIPTION_COLUMN]
COUNT_LABEL = "maintenances"
# Cumulative curves per machine (value, time, title).
CUMULATIVE = [
    (
        config.MAINTENANCE_DURATION_COLUMN,
        config.MAINTENANCE_TIMESTAMP_COLUMN,
        "Cumulative maintenance hours by machine",
    )
]
# Whole-source overview: proactive / reactive maintenance counts over time per machine.
OVERVIEW = overview.maintenance_overview_plots

PROCESSING = ProcessingConfig(
    encode={config.MAINTENANCE_TYPE_COLUMN: {"proactive": 0, "reactive": 1}, "component": None},
    impute={},
    outliers=[config.MAINTENANCE_DURATION_COLUMN],
)


def load_bronze(input_path=None):
    """Raw maintenance DataFrame (machine_code renamed to machine_id)."""
    engine = build_engine(input_path or config.DEFAULT_MACHINES_SQL)
    return load_maintenance(engine)


def to_silver(bronze_df):
    """Declared processing + denormalised machine-dimension attributes (star schema)."""
    df, _ = apply_processing(bronze_df, PROCESSING)
    referential = load_machine_referential(build_engine())
    attributes = [config.MACHINE_COLUMN, *config.MACHINE_ENRICH_COLUMNS]
    df = df.merge(referential[attributes], on=config.MACHINE_COLUMN, how="left")
    return df
