"""Telemetry source — bronze/silver builders for the medallion orchestrator.

- Bronze : raw typed telemetry (no PII).
- Silver : treatment only (dedup, per-machine time interpolation, z-score; no outlier clip).
- Gold   : telemetry is the spine of the unified Gold table (src/gold/features.py); capacity
  features (over_capacity_flag, utilization) are derived there at the (machine, hour) grain.
"""

from __future__ import annotations

import logging

from src import config
from src.framework.processing.pipeline import ProcessingConfig, apply_processing
from src.usecase.ingestion.schemas import TelemetryRow
from src.usecase.sources.telemetry import overview
from src.usecase.sources.telemetry.loader import load_telemetry

logger = logging.getLogger(__name__)

SOURCE_NAME = "telemetry"
TABLE = "telemetry"
MODEL = TelemetryRow  # Bronze validation/flagging schema
DUP_KEYS = [config.MACHINE_COLUMN, config.TELEMETRY_TIMESTAMP_COLUMN]  # (machine, hour)
RAW_REF = "telemetry.csv"  # DataLake input (lineage)
GOLD_ROLE = "telemetry"  # spine of the unified Gold table
# Physical measures (the 5 params minus the piece count, treated separately).
MEASURES = [c for c in config.TELEMETRY_PARAM_COLUMNS if c != config.TELEMETRY_PIECES_COLUMN]
BRONZE_NUMERIC = list(config.TELEMETRY_PARAM_COLUMNS)
SILVER_NUMERIC = list(config.TELEMETRY_PARAM_COLUMNS)
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
    # Telemetry is an hourly per-machine series: fill gaps by time interpolation within each
    # machine. A global median would instead inject an artificial spike at the median value.
    interpolate={
        "group": config.MACHINE_COLUMN,
        "time": config.TELEMETRY_TIMESTAMP_COLUMN,
        "columns": list(MEASURES),
        "method": "time",
    },
    # Outliers intentionally NOT clipped: IQR winsorisation piled mass at the fence (an
    # artificial spike at the distribution end). Raw extremes are kept for analysis.
    normalize={param: "zscore" for param in MEASURES},
)


def load_bronze(input_path=None):
    """Raw telemetry DataFrame."""
    return load_telemetry(input_path or config.DEFAULT_TELEMETRY_CSV)


def to_silver(bronze_df):
    """Treatment only: dedup + per-machine time interpolation + z-score on the measures.

    ``pieces_produced`` is kept raw. Returns ``(silver_df, report)``.
    """
    return apply_processing(bronze_df, PROCESSING)
