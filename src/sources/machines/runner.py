"""Machines/maintenance source — bronze/silver builders for the orchestrator.

- Bronze : maintenance events loaded from the SQL dump (no PII).
- Silver : declared processing (encode type/component, IQR outlier clipping on duration)
  + enrichment with the machine dimension attributes (criticality, line, location, ...).
"""

from __future__ import annotations

import logging

import pandas as pd

from src import config
from src.processing.pipeline import ProcessingConfig, apply_processing
from src.sources.machines import overview
from src.sources.machines.loader import build_engine, load_machine_referential, load_maintenance

logger = logging.getLogger(__name__)

SOURCE_NAME = "machines"
TABLE = "maintenance"
BRONZE_NUMERIC = [config.MAINTENANCE_DURATION_COLUMN]
# machine_age_years is Silver-only (derived) -> box/dist by analogy with duration_hours.
SILVER_NUMERIC = [config.MAINTENANCE_DURATION_COLUMN, "machine_age_years"]
# Maintenance count per category (descending; horizontal bars beyond 20 modalities).
# The dimension attributes + calendar features are Silver-only (merged / derived), so they
# render in the Silver layer by analogy with component/description and the machine dimension.
COUNT_FEATURES = [
    config.MAINTENANCE_COMPONENT_COLUMN,
    config.MAINTENANCE_DESCRIPTION_COLUMN,
    config.MACHINE_CRITICALITY_COLUMN,
    config.MACHINE_LINE_COLUMN,
    config.MACHINE_LOCATION_COLUMN,
    config.MACHINE_MODEL_COLUMN,
    "hour",
    "weekday",
    "month",
    # Silver-only 0/1 flag: a count bar (0 vs 1) visualises the engineered feature.
    "is_weekend",
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


def _engineer(df: pd.DataFrame) -> pd.DataFrame:
    """Derive calendar features from maintenance_at and machine_age_years from commissioning."""
    df = df.copy()
    at = pd.to_datetime(df[config.MAINTENANCE_TIMESTAMP_COLUMN], errors="coerce")
    if at.dt.tz is not None:
        at = at.dt.tz_localize(None)
    df["hour"] = at.dt.hour.astype("Int64")
    df["weekday"] = at.dt.weekday.astype("Int64")
    df["month"] = at.dt.month.astype("Int64")
    df["is_weekend"] = (at.dt.weekday >= 5).astype("Int64")
    if config.MACHINE_COMMISSIONING_COLUMN in df.columns:
        commissioned = pd.to_datetime(df[config.MACHINE_COMMISSIONING_COLUMN], errors="coerce")
        if commissioned.dt.tz is not None:
            commissioned = commissioned.dt.tz_localize(None)
        df["machine_age_years"] = ((at - commissioned).dt.days / 365.25).round(2)
    return df


def load_bronze(input_path=None):
    """Raw maintenance DataFrame (machine_code renamed to machine_id)."""
    engine = build_engine(input_path or config.DEFAULT_MACHINES_SQL)
    return load_maintenance(engine)


def to_silver(bronze_df):
    """Merge the machine dimension first, engineer features, then process; ``(df, report)``.

    Star schema: every machine attribute (incl. commissioning_date) is denormalised into
    each maintenance row, then calendar features + machine_age are derived and the declared
    encodings applied (maintenance's own + the merged dimension attributes).
    """
    referential = load_machine_referential(build_engine())
    df = bronze_df.merge(referential, on=config.MACHINE_COLUMN, how="left")
    df = _engineer(df)
    df, report = apply_processing(df, PROCESSING)
    return df, report
