"""Unit tests for the Gold experiment harness (versioning + manifest + params override)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import config
from src.usecase.gold.experiment import build_gold_version, dataset_version


def _silver():
    ts = pd.date_range("2025-01-01", periods=12, freq="h")
    telemetry = pd.DataFrame(
        {
            config.MACHINE_COLUMN: "MACH-01",
            config.TELEMETRY_TIMESTAMP_COLUMN: ts,
            **{m: np.linspace(1.0, 2.0, 12) for m in config.TELEMETRY_PARAM_COLUMNS},
        }
    )
    incidents = pd.DataFrame(
        {
            config.MACHINE_COLUMN: ["MACH-01"],
            config.DATE_COLUMN: ["2025-01-01"],
            config.TIME_COLUMN: ["05:00:00"],
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


def test_dataset_version_is_deterministic_and_param_sensitive():
    assert dataset_version({"a": 1, "b": 2}) == dataset_version({"b": 2, "a": 1})  # key order
    assert dataset_version({"failure_severity_min": 4}) != dataset_version(
        {"failure_severity_min": 5}
    )


def test_build_gold_version_threshold_changes_labels_and_id():
    silver = _silver()
    _, default = build_gold_version(silver, params=None)  # threshold 4 -> sev-5 is a failure
    _, high = build_gold_version(silver, params={"failure_severity_min": 6})  # nothing qualifies

    assert default["dataset_version"] != high["dataset_version"]
    assert default["rows"] == high["rows"]
    assert default["label_positive_rate"]["label_failure_next_6h"] > 0
    assert high["label_positive_rate"]["label_failure_next_6h"] == 0
    assert set(default).issuperset({"content_hash", "split", "label_censored", "params"})
