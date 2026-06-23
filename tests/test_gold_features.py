"""Unit tests for the unified Gold builder (grain, feature groups, no-leakage labels)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import config
from src.usecase.gold.features import (
    EVENT_H,
    FAILURE_SEVERITY_MIN,
    LABEL_H,
    WE,
    WS,
    build_gold_features,
    load_gold_params,
)


def test_gold_params_load_with_reference_defaults():
    p = load_gold_params()
    assert FAILURE_SEVERITY_MIN == 4
    assert [h for _, h in LABEL_H] == [6, 12, 24, 48]
    assert [lab for lab, _ in EVENT_H] == ["6h", "12h", "24h", "48h", "7d"]
    assert p["memory_horizons_h"] == [2, 3, 4, 6, 12, 24, 48]


BASE = pd.Timestamp("2025-01-01 00:00:00")
N_HOURS = 30
FAIL_HOUR = 9  # an incident of severity 5 occurs at this hour


def _synthetic_silver():
    """One machine, 30 contiguous hourly telemetry rows; one failure incident at FAIL_HOUR."""
    ts = pd.date_range(BASE, periods=N_HOURS, freq="h")
    telemetry = pd.DataFrame(
        {
            config.MACHINE_COLUMN: "MACH-01",
            config.TELEMETRY_TIMESTAMP_COLUMN: ts,
            **{m: np.linspace(1.0, 2.0, N_HOURS) for m in config.TELEMETRY_PARAM_COLUMNS},
        }
    )
    incidents = pd.DataFrame(
        {
            config.MACHINE_COLUMN: ["MACH-01"],
            config.DATE_COLUMN: ["2025-01-01"],
            config.TIME_COLUMN: [f"{FAIL_HOUR:02d}:00:00"],
            config.SEVERITY_COLUMN: [5],
            **{s: [0] for s in config.SIGNAL_COLUMNS},
        }
    )
    maintenance = pd.DataFrame(
        {
            config.MACHINE_COLUMN: ["MACH-01"],
            config.MAINTENANCE_TIMESTAMP_COLUMN: ["2025-01-01 02:00:00"],
            config.MAINTENANCE_TYPE_COLUMN: ["reactive"],
        }
    )
    return {"telemetry": telemetry, "incidents": incidents, "maintenance": maintenance}


def test_grain_is_unique_per_machine_hour():
    gold = build_gold_features(_synthetic_silver())
    assert gold.duplicated([config.MACHINE_COLUMN, WS]).sum() == 0
    assert len(gold) == N_HOURS
    assert (gold[WE] - gold[WS] == pd.Timedelta(hours=1)).all()


def test_feature_groups_present():
    gold = build_gold_features(_synthetic_silver())
    expected = {
        "temperature_c_mean_24h",  # memory
        "temperature_c_trend_6h",  # trend
        "temperature_c_z_machine",  # anomaly
        "inc_count_24h",  # context (incidents)
        "mnt_corr_count_30d",  # context (maintenance)
        "label_failure_next_6h",  # label
    }
    assert expected <= set(gold.columns)


def test_label_failure_next_6h_no_leakage():
    gold = build_gold_features(_synthetic_silver()).set_index(WS)
    label = gold["label_failure_next_6h"]
    # Failure at FAIL_HOUR=9 is visible 6h ahead: row at hour 3 sees it (9 in (3, 9]).
    assert label.loc[BASE + pd.Timedelta(hours=3)] == 1
    # Hour 0 looks at (0, 6] -> no failure.
    assert label.loc[BASE + pd.Timedelta(hours=0)] == 0
    # Hour 27: window (27, 33] extends past the last observed hour (29) -> censored -> NaN.
    assert pd.isna(label.loc[BASE + pd.Timedelta(hours=27)])
