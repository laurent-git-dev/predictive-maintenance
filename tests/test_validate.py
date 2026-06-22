"""Unit tests for the Bronze validation/flagging (parse_ok / parse_reason; no mutation)."""

from __future__ import annotations

import pandas as pd

from src import config
from src.ingestion.schemas import IncidentRow
from src.ingestion.validate import PARSE_OK, PARSE_REASON, validate_and_flag


def _base_row(incident_id="I1", **overrides):
    row = {
        config.ID_COLUMN: incident_id,
        config.DATE_COLUMN: "2025-01-01",
        config.TIME_COLUMN: "08:00:00",
        config.OPERATOR_NAME_COLUMN: "abc123",
        config.OPERATOR_BADGE_COLUMN: "def456",
        config.MACHINE_COLUMN: "MACH-01",
        config.SEVERITY_COLUMN: 3,
        config.COMMENT_COLUMN: "ok",
        config.SHIFT_COLUMN: "matin",
        **{s: 0 for s in config.SIGNAL_COLUMNS},
    }
    row.update(overrides)
    return row


def _flag(rows):
    return validate_and_flag(pd.DataFrame(rows), IncidentRow, [config.ID_COLUMN])


def test_valid_row_is_parse_ok():
    out = _flag([_base_row()])
    assert bool(out[PARSE_OK].iloc[0]) is True
    assert out[PARSE_REASON].iloc[0] == ""


def test_out_of_domain_shift_flagged():
    out = _flag([_base_row(shift="bogus")])
    assert bool(out[PARSE_OK].iloc[0]) is False
    assert "domain:shift" in out[PARSE_REASON].iloc[0]


def test_missing_required_value_flagged_as_missing():
    out = _flag([_base_row(severity=None)])
    assert bool(out[PARSE_OK].iloc[0]) is False
    assert "missing:severity" in out[PARSE_REASON].iloc[0]


def test_out_of_range_severity_flagged_as_range():
    out = _flag([_base_row(severity=9)])  # domain is 1..5
    assert "range:severity" in out[PARSE_REASON].iloc[0]


def test_duplicate_key_flagged_on_second_occurrence():
    out = _flag([_base_row("I1"), _base_row("I2"), _base_row("I1")])
    reasons = out[PARSE_REASON].tolist()
    assert reasons[0] == "" and reasons[1] == ""  # first occurrences clean
    assert reasons[2] == "duplicate"  # second I1


def test_validation_does_not_modify_values():
    df = pd.DataFrame([_base_row(shift="bogus", severity=None)])
    out = validate_and_flag(df, IncidentRow, [config.ID_COLUMN])
    pd.testing.assert_frame_equal(out.drop(columns=[PARSE_OK, PARSE_REASON]), df)
