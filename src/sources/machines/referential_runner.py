"""Machine referential (dimension) — bronze/silver builders for the orchestrator.

The ``machine`` table from the SQL dump is a **dimension** (one row per machine):
- Bronze : raw referential (coherence checks: PK, criticality domain, capacities, dates).
- Silver : lightly cleaned dimension (criticality encoded to an ordinal ``criticality_code``).

It is a static dimension (one row per machine), so per-machine boxplots are skipped
(``MACHINE_COL = ""``); numeric capacities get a distribution and the categorical
attributes a count chart.
"""

from __future__ import annotations

import logging

from src import config
from src.processing.pipeline import ProcessingConfig
from src.sources.machines import overview
from src.sources.machines.loader import build_engine, load_machine_referential

logger = logging.getLogger(__name__)

SOURCE_NAME = "machine"
TABLE = config.MACHINE_TABLE
# Dimension consumed only as a Bronze referential: its attributes are denormalised into
# silver.maintenance (merge-first star schema), so it has no standalone Silver table.
BRONZE_ONLY = True
# Dimension: one row per machine -> no per-machine boxplot (no grouping column).
MACHINE_COL = ""
# Capacities are shown as a bar per machine (descending), not a distribution.
BRONZE_NUMERIC = []
SILVER_NUMERIC = []
BARS_BY_MACHINE = [config.MACHINE_MAX_DAILY_COLUMN, config.MACHINE_MAX_HOURLY_COLUMN]
COUNT_FEATURES = [
    config.MACHINE_CRITICALITY_COLUMN,
    config.MACHINE_MODEL_COLUMN,
    config.MACHINE_LINE_COLUMN,
    config.MACHINE_LOCATION_COLUMN,
]
COUNT_LABEL = "machines"
# Extra per-feature plot: capacity coherence (hourly vs daily) under max_hourly_capacity_pieces.
FEATURE_PLOTS = {config.MACHINE_MAX_HOURLY_COLUMN: overview.plot_capacity_coherence}

# Bronze-only: no Silver processing here. The dimension's encodings (criticality, ...) are
# applied where it is consumed — denormalised into silver.maintenance.
PROCESSING = ProcessingConfig()


def load_bronze(input_path=None):
    """Raw machine referential DataFrame (one row per machine)."""
    engine = build_engine(input_path or config.DEFAULT_MACHINES_SQL)
    return load_machine_referential(engine)


def to_silver(bronze_df):
    """Bronze-only source: no standalone Silver table (kept for contract). ``(df, report)``."""
    return bronze_df, {}
