"""Machines/maintenance source — bronze/silver builders for the orchestrator.

- Bronze : maintenance events loaded from the SQL dump (no PII).
- Silver : enrichment with the machine dimension attributes (criticality, line, location, ...)
  + declared encodings (type/action/component + dimension attributes).
- Gold   : handled by the unified builder (src/gold/features.py); maintenance events are
  aggregated to the (machine, hour) grain there (calendar / machine_age computed on the grid).
"""

from __future__ import annotations

import logging

from src import config
from src.ingestion.schemas import MaintenanceRow
from src.processing.pipeline import ProcessingConfig, apply_processing
from src.sources.machines import overview
from src.sources.machines.loader import build_engine, load_machine_referential, load_maintenance

logger = logging.getLogger(__name__)

SOURCE_NAME = "machines"
TABLE = "maintenance"
MODEL = MaintenanceRow  # Bronze validation/flagging schema
DUP_KEYS = [config.MAINTENANCE_ID_COLUMN]  # duplicate detection key
RAW_REF = "machines.sql"  # DataLake input (lineage)
GOLD_ROLE = "maintenance"  # feeds the unified Gold builder's maintenance slot
BRONZE_NUMERIC = [config.MAINTENANCE_DURATION_COLUMN]
SILVER_NUMERIC = [config.MAINTENANCE_DURATION_COLUMN]
# Maintenance count per category (descending; horizontal bars beyond 20 modalities).
# The dimension attributes are merged into Silver. Calendar / age features now live in the
# unified Gold table (built per (machine, hour) by src/gold/features.py).
COUNT_FEATURES = [
    config.MAINTENANCE_COMPONENT_COLUMN,
    config.MAINTENANCE_DESCRIPTION_COLUMN,
    config.MACHINE_CRITICALITY_COLUMN,
    config.MACHINE_LINE_COLUMN,
    config.MACHINE_LOCATION_COLUMN,
    config.MACHINE_MODEL_COLUMN,
]
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

# Merge-first star schema: the machine dimension is denormalised into each maintenance
# row, then every feature (maintenance's own + the merged dimension attributes) is treated.
PROCESSING = ProcessingConfig(
    encode={
        config.MAINTENANCE_TYPE_COLUMN: {"proactive": 0, "reactive": 1},
        config.MAINTENANCE_ACTION_COLUMN: None,
        config.MAINTENANCE_COMPONENT_COLUMN: None,
        config.MACHINE_CRITICALITY_COLUMN: config.CRITICALITY_ORDER,
        config.MACHINE_LINE_COLUMN: None,
        config.MACHINE_LOCATION_COLUMN: None,
        config.MACHINE_MODEL_COLUMN: None,
    },
)


def load_bronze(input_path=None):
    """Raw maintenance DataFrame (machine_code renamed to machine_id)."""
    engine = build_engine(input_path or config.DEFAULT_MACHINES_SQL)
    return load_maintenance(engine)


def to_silver(bronze_df):
    """Merge the machine dimension (star schema), then apply the encodings; ``(df, report)``.

    Every machine attribute (incl. commissioning_date) is denormalised into each maintenance
    row, then the declared encodings are applied (maintenance's own + dimension attributes).
    Feature engineering (calendar, machine_age_years) happens in Gold.
    """
    referential = load_machine_referential(build_engine())
    df = bronze_df.merge(referential, on=config.MACHINE_COLUMN, how="left")
    return apply_processing(df, PROCESSING)
