"""Cross-source join builders.

These reuse the **source loaders** (no duplication) and join everything on the
universal key ``machine_id`` (and ``incident_id`` for the maintenance link).
"""

from __future__ import annotations

import logging

import pandas as pd

from src import config
from src.usecase.sources.incidents.loader import load_incidents
from src.usecase.sources.incidents.pipeline import add_confidence_index
from src.usecase.sources.machines.loader import (
    build_engine,
    load_machine_referential,
    load_maintenance,
)
from src.usecase.sources.telemetry.loader import load_telemetry

logger = logging.getLogger(__name__)


def load_sources(
    incidents_path=None, telemetry_path=None, machines_path=None
) -> dict[str, pd.DataFrame]:
    """Load every source into DataFrames via their own loaders.

    Incidents are loaded raw (no anonymisation needed: we only use non-PII
    columns) and enriched with the confidence index.
    """
    incidents = add_confidence_index(load_incidents(incidents_path or config.DEFAULT_INPUT_CSV))
    telemetry = load_telemetry(telemetry_path or config.DEFAULT_TELEMETRY_CSV)
    engine = build_engine(machines_path or config.DEFAULT_MACHINES_SQL)
    return {
        "incidents": incidents,
        "telemetry": telemetry,
        "maintenance": load_maintenance(engine),
        "machine_ref": load_machine_referential(engine),
    }


def build_machine_profile(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per machine combining incidents, telemetry and maintenance."""
    m = config.MACHINE_COLUMN
    inc = sources["incidents"].copy()
    inc[config.SEVERITY_COLUMN] = pd.to_numeric(inc[config.SEVERITY_COLUMN], errors="coerce")
    tel = sources["telemetry"]
    maint = sources["maintenance"]
    ref = sources["machine_ref"]

    inc_agg = inc.groupby(m).agg(
        n_incidents=(config.ID_COLUMN, "count"),
        mean_severity=(config.SEVERITY_COLUMN, "mean"),
        mean_confidence=(config.CONFIDENCE_COLUMN, "mean"),
    )
    tel_params = [c for c in config.TELEMETRY_PARAM_COLUMNS if c in tel.columns]
    tel_agg = tel.groupby(m)[tel_params].mean().add_prefix("mean_")
    maint_agg = maint.groupby(m).agg(
        n_maintenance=("maintenance_id", "count"),
        mean_duration=(config.MAINTENANCE_DURATION_COLUMN, "mean"),
    )
    n_reactive = (
        maint[maint[config.MAINTENANCE_TYPE_COLUMN] == "reactive"]
        .groupby(m)
        .size()
        .rename("n_reactive")
    )

    profile = (
        ref.set_index(m)[[config.MACHINE_CRITICALITY_COLUMN, "production_line"]]
        .join([inc_agg, tel_agg, maint_agg, n_reactive])
        .reset_index()
    )
    for col in ["n_incidents", "n_maintenance", "n_reactive"]:
        if col in profile.columns:
            profile[col] = profile[col].fillna(0).astype(int)
    return profile.round(3)


def build_reactive_incident_join(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Join reactive maintenances to the incident that triggered them.

    ``maintenance.related_incident_id`` -> ``incidents.incident_id``.
    """
    inc = sources["incidents"].copy()
    inc[config.SEVERITY_COLUMN] = pd.to_numeric(inc[config.SEVERITY_COLUMN], errors="coerce")
    maint = sources["maintenance"]

    reactive = maint[
        (maint[config.MAINTENANCE_TYPE_COLUMN] == "reactive")
        & maint[config.MAINTENANCE_INCIDENT_COLUMN].notna()
    ]
    joined = reactive.merge(
        inc[[config.ID_COLUMN, config.SEVERITY_COLUMN]],
        left_on=config.MAINTENANCE_INCIDENT_COLUMN,
        right_on=config.ID_COLUMN,
        how="inner",
    )
    logger.info(
        "Reactive↔incident join: %d of %d reactive maintenances matched an incident.",
        len(joined),
        len(reactive),
    )
    return joined
