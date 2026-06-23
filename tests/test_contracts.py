"""Data-contract tests for the 4 Bronze sources.

1. **Schema ↔ ORM drift guard** — the Pydantic contract and the SQLAlchemy Bronze ORM must
   stay in lockstep (same data columns; optional contract fields ⇒ nullable columns). This
   enforces a single source of truth without dynamically generating the ORM (which would fight
   the Alembic-managed DDL — specific VARCHAR lengths / column types Pydantic doesn't carry).
2. **parse_reason contract** — representative invalid rows must produce the expected, stable
   reason tokens per source (the validation behaviour is pinned and versioned).
"""

from __future__ import annotations

import pandas as pd
import pytest

from src import config
from src.framework.ingestion.validate import PARSE_OK, PARSE_REASON, validate_and_flag
from src.usecase.db.models_bronze import (
    BronzeIncident,
    BronzeMachine,
    BronzeMaintenance,
    BronzeTelemetry,
)
from src.usecase.ingestion.schemas import CONTRACT_VERSION
from src.usecase.sources.registry import SPECS_BY_NAME

_FLAG_COLUMNS = {"id", PARSE_OK, PARSE_REASON}
# source name -> Bronze ORM class
_ORM = {
    "incidents": BronzeIncident,
    "telemetry": BronzeTelemetry,
    "machine": BronzeMachine,
    "machines": BronzeMaintenance,
}


def test_contract_version_is_declared():
    assert isinstance(CONTRACT_VERSION, int) and CONTRACT_VERSION >= 1


@pytest.mark.parametrize("name", list(_ORM))
def test_orm_matches_pydantic_contract(name):
    model = SPECS_BY_NAME[name].model
    orm_columns = {c.name: c for c in _ORM[name].__table__.columns}

    # (a) flag columns present; data columns are exactly the contract's fields.
    assert _FLAG_COLUMNS <= set(orm_columns)
    data_columns = set(orm_columns) - _FLAG_COLUMNS
    assert data_columns == set(model.model_fields), f"{name}: ORM/Pydantic field drift"

    # (b) a field that is optional in the contract must be nullable in the ORM.
    for field, info in model.model_fields.items():
        if not info.is_required():
            assert orm_columns[field].nullable, f"{name}.{field}: optional in contract but NOT NULL"


# --- parse_reason contract: representative invalid rows -> expected token --------------
def _valid_rows():
    sig = {s: 0 for s in config.SIGNAL_COLUMNS}
    return {
        "incidents": {
            config.ID_COLUMN: "I1",
            config.DATE_COLUMN: "2025-01-01",
            config.TIME_COLUMN: "08:00:00",
            config.OPERATOR_NAME_COLUMN: "a",
            config.OPERATOR_BADGE_COLUMN: "b",
            config.MACHINE_COLUMN: "MACH-01",
            config.SEVERITY_COLUMN: 3,
            config.COMMENT_COLUMN: "ok",
            config.SHIFT_COLUMN: "matin",
            **sig,
        },
        "telemetry": {
            config.MACHINE_COLUMN: "MACH-01",
            config.TELEMETRY_TIMESTAMP_COLUMN: "2025-01-01 00:00:00",
            "temperature_c": 1.0,
            "pressure_bar": 1.0,
            "voltage_mean_v": 1.0,
            "rotation_mean_rpm": 1.0,
            config.TELEMETRY_PIECES_COLUMN: 5,
        },
        "machine": {
            config.MACHINE_COLUMN: "MACH-01",
            config.MACHINE_COMMISSIONING_COLUMN: "2020-01-01",
            config.MACHINE_MAX_DAILY_COLUMN: 100,
            config.MACHINE_MAX_HOURLY_COLUMN: 10,
            config.MACHINE_MODEL_COLUMN: "m",
            config.MACHINE_LINE_COLUMN: "L1",
            config.MACHINE_LOCATION_COLUMN: "here",
            config.MACHINE_CRITICALITY_COLUMN: "LOW",
        },
        "machines": {
            config.MAINTENANCE_ID_COLUMN: 1,
            config.MACHINE_COLUMN: "MACH-01",
            config.MAINTENANCE_TIMESTAMP_COLUMN: "2025-01-01 00:00:00",
            config.MAINTENANCE_TYPE_COLUMN: "reactive",
            config.MAINTENANCE_ACTION_COLUMN: "fix",
            config.MAINTENANCE_COMPONENT_COLUMN: "motor",
            config.MAINTENANCE_DURATION_COLUMN: 1.0,
        },
    }


_CASES = [
    ("incidents", {config.SEVERITY_COLUMN: None}, "missing:severity"),
    ("incidents", {config.SEVERITY_COLUMN: 9}, "range:severity"),
    ("incidents", {config.SHIFT_COLUMN: "bogus"}, "domain:shift"),
    ("telemetry", {config.MACHINE_COLUMN: "BAD"}, "format:machine_id"),
    ("telemetry", {config.TELEMETRY_PIECES_COLUMN: -1}, "range:pieces_produced"),
    ("machine", {config.MACHINE_CRITICALITY_COLUMN: "EXTREME"}, "domain:criticality"),
    ("machine", {config.MACHINE_MAX_DAILY_COLUMN: 0}, "range:max_daily_capacity"),
    ("machines", {config.MAINTENANCE_TYPE_COLUMN: "weird"}, "domain:maintenance_type"),
    ("machines", {config.MAINTENANCE_DURATION_COLUMN: -1.0}, "range:duration_hours"),
]


@pytest.mark.parametrize("name,override,expected_token", _CASES)
def test_parse_reason_contract(name, override, expected_token):
    row = {**_valid_rows()[name], **override}
    spec = SPECS_BY_NAME[name]
    out = validate_and_flag(pd.DataFrame([row]), spec.model, spec.dup_keys)
    assert bool(out[PARSE_OK].iloc[0]) is False
    assert expected_token in out[PARSE_REASON].iloc[0]


@pytest.mark.parametrize("name", list(_ORM))
def test_valid_row_passes_for_every_source(name):
    spec = SPECS_BY_NAME[name]
    out = validate_and_flag(pd.DataFrame([_valid_rows()[name]]), spec.model, spec.dup_keys)
    assert bool(out[PARSE_OK].iloc[0]) is True
    assert out[PARSE_REASON].iloc[0] == ""
