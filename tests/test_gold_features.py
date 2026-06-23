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
            config.TELEMETRY_INTERPOLATED_COLUMN: 0,  # coverage flag (carried from Silver)
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
            # Static machine-dimension attributes (denormalised in silver.maintenance).
            "criticality_code": [2],
            "model_code": [1],
            "production_line_code": [0],
            "location_code": [3],
            config.MACHINE_MAX_DAILY_COLUMN: [240],
            config.MACHINE_MAX_HOURLY_COLUMN: [10],
            config.MACHINE_COMMISSIONING_COLUMN: ["2020-01-01"],
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
        "temperature_c_z_hist",  # anomaly (causal, vs history so far)
        "inc_count_24h",  # context (incidents)
        "mnt_corr_count_30d",  # context (maintenance)
        "fail_count_24h",  # recurrence (past failures)
        "failure_now",  # eligibility flag
        "machine_criticality_code",  # machine context
        "machine_age_years",  # machine context
        "utilization",  # load
        "over_capacity_flag",  # load
        "hour_sin",  # calendar
        "is_weekend",  # calendar
        "power_proxy",  # physics
        "co_anomaly_24h",  # physics
        "temperature_c_drift_baseline",  # drift vs healthy baseline
        "interp_frac_24h",  # data coverage
        "label_failure_next_6h",  # label
    }
    assert expected <= set(gold.columns)
    # The leaky global z-score must be gone.
    assert not any(c.endswith("_z_machine") for c in gold.columns)


def test_label_failure_next_6h_no_leakage():
    gold = build_gold_features(_synthetic_silver()).set_index(WS)
    label = gold["label_failure_next_6h"]
    # Failure at FAIL_HOUR=9 is visible 6h ahead: row at hour 3 sees it (9 in (3, 9]).
    assert label.loc[BASE + pd.Timedelta(hours=3)] == 1
    # Hour 0 looks at (0, 6] -> no failure.
    assert label.loc[BASE + pd.Timedelta(hours=0)] == 0
    # Hour 27: window (27, 33] extends past the last observed hour (29) -> censored -> NaN.
    assert pd.isna(label.loc[BASE + pd.Timedelta(hours=27)])


def test_z_hist_is_causal_no_future_leak():
    """z_hist of early rows must not change when only FUTURE telemetry changes (expanding stat)."""
    base = _synthetic_silver()
    spiked = _synthetic_silver()
    temp = spiked["telemetry"]["temperature_c"].to_numpy().copy()
    temp[20:] += 100.0  # perturb only hours >= 20
    spiked["telemetry"]["temperature_c"] = temp

    a = build_gold_features(base).set_index(WS)["temperature_c_z_hist"]
    b = build_gold_features(spiked).set_index(WS)["temperature_c_z_hist"]
    early = [BASE + pd.Timedelta(hours=h) for h in range(2, 20)]  # before the perturbation
    pd.testing.assert_series_equal(a.loc[early], b.loc[early])


def test_split_set_is_temporal_and_partitions():
    gold = build_gold_features(_synthetic_silver())
    assert set(gold["split_set"].unique()) == {"train", "val", "test"}
    train_max = gold.loc[gold["split_set"] == "train", WS].max()
    test_min = gold.loc[gold["split_set"] == "test", WS].min()
    assert train_max < test_min  # temporal: train strictly precedes test


def test_time_to_failure_label():
    gold = build_gold_features(_synthetic_silver()).set_index(WS)
    ttf = gold["label_ttf_hours"]
    assert ttf.loc[BASE] == 9  # failure at hour 9
    assert ttf.loc[BASE + pd.Timedelta(hours=8)] == 1
    assert pd.isna(ttf.loc[BASE + pd.Timedelta(hours=9)])  # nothing strictly after hour 9
    assert gold["label_ttf_censored"].loc[BASE + pd.Timedelta(hours=9)] == 1


def test_failure_refractory_collapses_onsets(monkeypatch):
    silver = _synthetic_silver()
    extra = silver["incidents"].iloc[[0]].copy()
    extra[config.TIME_COLUMN] = "11:00:00"  # a second failure 2h after the first
    silver["incidents"] = pd.concat([silver["incidents"], extra], ignore_index=True)

    # No refractory: from hour 10 the next failure is at hour 11 -> TTF = 1.
    base = build_gold_features(silver).set_index(WS)
    assert base["label_ttf_hours"].loc[BASE + pd.Timedelta(hours=10)] == 1

    # Refractory 5h: the failure at 11 is within 5h of the one at 9, so it is NOT a new onset
    # -> no onset strictly after hour 10 -> censored.
    monkeypatch.setattr("src.usecase.gold.features.FAILURE_REFRACTORY_H", 5)
    refr = build_gold_features(silver).set_index(WS)
    assert pd.isna(refr["label_ttf_hours"].loc[BASE + pd.Timedelta(hours=10)])
