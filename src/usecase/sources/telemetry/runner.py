"""Telemetry source — bronze/silver builders for the medallion orchestrator.

- Bronze : raw typed telemetry (no PII).
- Silver : treatment only (dedup, per-machine time interpolation, z-score; no outlier clip).
- Gold   : telemetry is the spine of the unified Gold table (src/gold/features.py); capacity
  features (over_capacity_flag, utilization) are derived there at the (machine, hour) grain.
"""

from __future__ import annotations

import logging

import yaml

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


def _make_processing(interpolate: bool = True, clip_outliers: bool = False) -> ProcessingConfig:
    """Telemetry Silver config. Defaults reproduce the reference treatment; the two flags are
    experiment knobs (params.yaml → ``silver.telemetry``):

    - ``interpolate=False`` -> leave gaps as NaN (NaN-aware variant; no coverage flag).
    - ``clip_outliers=True`` -> IQR-winsorise the measures (the behaviour that piled mass at the
      fence — kept off by default, available for comparison).
    """
    cfg: dict = {
        "dedup": {
            "keys": [config.MACHINE_COLUMN, config.TELEMETRY_TIMESTAMP_COLUMN],
            "strategy": "mean",
        },
        "normalize": {param: "zscore" for param in MEASURES},
    }
    if interpolate:
        cfg["interpolate"] = {
            "group": config.MACHINE_COLUMN,
            "time": config.TELEMETRY_TIMESTAMP_COLUMN,
            "columns": list(MEASURES),
            "method": "time",
            "flag": config.TELEMETRY_INTERPOLATED_COLUMN,  # mark filled rows (data coverage)
        }
    if clip_outliers:
        cfg["outliers"] = list(MEASURES)
    return ProcessingConfig(**cfg)


# Default config (reference treatment) — also exposed to the registry for display.
PROCESSING = _make_processing()


def _silver_params() -> dict:
    """Read ``silver.telemetry`` overrides from params.yaml (empty = reference treatment)."""
    path = config.PROJECT_ROOT / "params.yaml"
    if not path.exists():
        return {}
    silver = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("silver") or {}
    return silver.get("telemetry") or {}


def load_bronze(input_path=None):
    """Raw telemetry DataFrame."""
    return load_telemetry(input_path or config.DEFAULT_TELEMETRY_CSV)


def to_silver(bronze_df):
    """Treatment only: dedup + per-machine time interpolation + z-score on the measures.

    ``pieces_produced`` is kept raw. Interpolation / outlier-clipping are configurable via
    ``params.yaml`` (``silver.telemetry``) for dataset experiments. Returns ``(silver_df, report)``.
    """
    p = _silver_params()
    cfg = _make_processing(
        interpolate=bool(p.get("interpolate", True)),
        clip_outliers=bool(p.get("clip_outliers", False)),
    )
    return apply_processing(bronze_df, cfg)
