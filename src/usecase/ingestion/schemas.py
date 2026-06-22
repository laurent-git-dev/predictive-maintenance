"""Pydantic row schemas for the 4 Bronze sources — used to **flag** invalid rows.

These models declare the expected **type**, **domain** and **basic constraints** per feature.
They are run row-by-row to *detect* anomalies (type, range/domain, missing); **no value is
ever modified** — the validation outcome is recorded in ``parse_ok`` / ``parse_reason`` only.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

_MACHINE_PATTERN = r"^MACH-\d{2,}$"
Signal = Annotated[int, Field(ge=0, le=1)]  # binary 0/1 flag


class _Row(BaseModel):
    model_config = ConfigDict(extra="ignore")  # ignore unknown columns


class IncidentRow(_Row):
    incident_id: str
    date: date
    time: time
    operator_name: str
    operator_badge: str
    machine_id: str = Field(pattern=_MACHINE_PATTERN)
    severity: Annotated[int, Field(ge=1, le=5)]
    comment: str | None = None
    shift: Literal["matin", "apres-midi", "nuit"]
    type_surchauffe: Signal
    type_baisse_pression: Signal
    type_vibration: Signal
    type_bruit_mecanique: Signal
    type_surconsommation: Signal
    type_blocage_mecanique: Signal
    type_alarme_capteur: Signal
    type_arret_urgence: Signal
    type_defaut_qualite: Signal


class TelemetryRow(_Row):
    machine_id: str = Field(pattern=_MACHINE_PATTERN)
    timestamp: datetime
    temperature_c: float
    pressure_bar: float
    voltage_mean_v: float
    rotation_mean_rpm: float
    pieces_produced: Annotated[int, Field(ge=0)]


class MachineRow(_Row):
    machine_id: str = Field(pattern=_MACHINE_PATTERN)
    commissioning_date: date
    max_daily_capacity: Annotated[int, Field(gt=0)]
    max_hourly_capacity_pieces: Annotated[int, Field(gt=0)]
    model: str
    production_line: str
    location: str
    criticality: Literal["LOW", "MEDIUM", "HIGH"]


class MaintenanceRow(_Row):
    maintenance_id: int
    machine_id: str = Field(pattern=_MACHINE_PATTERN)
    maintenance_at: datetime
    maintenance_type: Literal["proactive", "reactive"]
    action_type: str
    component: str
    description: str | None = None
    related_incident_id: str | None = None
    duration_hours: Annotated[float, Field(ge=0)]


# The source↔model↔duplicate-key mapping lives in the single registry (``SourceSpec.model`` /
# ``SourceSpec.dup_keys``); each source declares it in its runner.
