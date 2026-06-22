"""Telemetry source — bronze/silver builders for the medallion orchestrator.

- Bronze : raw typed telemetry (no PII).
- Silver : declared processing (median imputation + IQR outlier clipping).
"""

from __future__ import annotations

import logging

from src import config
from src.processing.pipeline import ProcessingConfig, apply_processing
from src.sources.machines.loader import build_engine, load_machine_referential
from src.sources.telemetry import overview
from src.sources.telemetry.loader import load_telemetry

logger = logging.getLogger(__name__)

SOURCE_NAME = "telemetry"
TABLE = "telemetry"
# Physical measures (the 5 params minus the piece count, treated separately).
MEASURES = [c for c in config.TELEMETRY_PARAM_COLUMNS if c != config.TELEMETRY_PIECES_COLUMN]
BRONZE_NUMERIC = list(config.TELEMETRY_PARAM_COLUMNS)
SILVER_NUMERIC = list(config.TELEMETRY_PARAM_COLUMNS)
# Silver-only 0/1 flag: a count bar (0 vs 1) visualises how many readings exceed capacity.
COUNT_FEATURES = ["over_capacity_flag"]
# Per-machine time series (value, time, title, freq): one mean line per machine.
TIMESERIES = [
    (
        config.TELEMETRY_PIECES_COLUMN,
        config.TELEMETRY_TIMESTAMP_COLUMN,
        "Average daily piece production by machine",
        "D",
    ),
    (
        config.TELEMETRY_PIECES_COLUMN,
        config.TELEMETRY_TIMESTAMP_COLUMN,
        "Average weekly piece production by machine",
        "W",
    ),
]
# Whole-source overview (measures over time).
OVERVIEW = overview.plots

PROCESSING = ProcessingConfig(
    # Reconcile conflicting duplicate readings for the same (machine, hour) by averaging.
    dedup={"keys": [config.MACHINE_COLUMN, config.TELEMETRY_TIMESTAMP_COLUMN], "strategy": "mean"},
    impute={param: "median" for param in MEASURES},
    outliers=list(MEASURES),
    normalize={param: "zscore" for param in MEASURES},
)


def load_bronze(input_path=None):
    """Raw telemetry DataFrame."""
    return load_telemetry(input_path or config.DEFAULT_TELEMETRY_CSV)


def to_silver(bronze_df):
    """Dedup + impute + IQR + z-score on measures, then add ``over_capacity_flag``.

    ``pieces_produced`` is kept raw; ``over_capacity_flag`` (0/1) marks readings whose
    production exceeds the machine's declared hourly capacity (from the referential).
    Returns ``(silver_df, report)``.
    """
    df, report = apply_processing(bronze_df, PROCESSING)
    capacity = load_machine_referential(build_engine())[
        [config.MACHINE_COLUMN, config.MACHINE_MAX_HOURLY_COLUMN]
    ]
    df = df.merge(capacity, on=config.MACHINE_COLUMN, how="left")
    df["over_capacity_flag"] = (
        df[config.TELEMETRY_PIECES_COLUMN] > df[config.MACHINE_MAX_HOURLY_COLUMN]
    ).astype("Int64")
    df = df.drop(columns=[config.MACHINE_MAX_HOURLY_COLUMN])
    return df, report
