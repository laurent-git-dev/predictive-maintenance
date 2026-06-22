"""Unit tests for the mutualised processing tools (small synthetic frames, no DB/data)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.processing.dedup import deduplicate
from src.processing.imputation import impute
from src.processing.interpolation import interpolate_by_group
from src.processing.normalization import normalize
from src.processing.outliers import treat_outliers
from src.processing.transformation import encode_categorical


def test_deduplicate_mean_reconciles_duplicates():
    df = pd.DataFrame({"k": ["a", "a", "b"], "v": [10.0, 20.0, 5.0]})
    out, report = deduplicate(df, ["k"], "mean")
    assert len(out) == 2
    assert report["n_removed"] == 1
    assert out.loc[out["k"] == "a", "v"].iloc[0] == 15.0  # (10+20)/2


def test_deduplicate_first_keeps_first_row():
    df = pd.DataFrame({"k": ["a", "a"], "v": [10, 20]})
    out, report = deduplicate(df, ["k"], "first")
    assert len(out) == 1 and out["v"].iloc[0] == 10 and report["n_removed"] == 1


def test_interpolate_by_group_fills_gaps_without_residual_nan():
    t = pd.date_range("2025-01-01", periods=5, freq="h")
    df = pd.DataFrame({"m": "M1", "ts": t, "x": [1.0, np.nan, 3.0, np.nan, 5.0]})
    out, report = interpolate_by_group(df, "m", "ts", ["x"])
    assert out["x"].isna().sum() == 0
    assert out["x"].tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert report["x"]["n_filled"] == 2


def test_impute_median_fills_only_missing():
    df = pd.DataFrame({"v": [1.0, np.nan, 3.0]})
    out, report = impute(df, {"v": "median"})
    assert out["v"].tolist() == [1.0, 2.0, 3.0]  # median of {1,3} = 2
    assert report["v"]["n_filled"] == 1


def test_treat_outliers_clips_to_iqr_fence():
    df = pd.DataFrame({"v": [10, 11, 12, 13, 1000]})  # 1000 is an upper outlier
    out, report = treat_outliers(df, ["v"])
    assert out["v"].max() < 1000
    assert report["v"]["n_clipped"] == 1
    assert out["v"].max() == report["v"]["high"]


def test_normalize_zscore_adds_norm_column_centered():
    df = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
    out, _ = normalize(df, {"v": "zscore"})
    assert "v_norm" in out.columns
    assert abs(out["v_norm"].mean()) < 1e-9
    assert "v" in out.columns and out["v"].tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]  # original kept


def test_encode_categorical_explicit_and_auto():
    df = pd.DataFrame({"s": ["lo", "hi", "lo"], "c": ["x", "y", "x"]})
    out, report = encode_categorical(df, {"s": {"lo": 0, "hi": 1}, "c": None})
    assert out["s_code"].tolist() == [0, 1, 0]  # explicit map
    assert report["s"]["code_column"] == "s_code"
    assert out["c_code"].tolist() == [0, 1, 0]  # auto codes (alphabetical: x=0, y=1)
    assert "s" in out.columns and "c" in out.columns  # originals preserved
