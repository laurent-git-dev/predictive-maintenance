"""Unit tests for the configurable telemetry Silver treatment (C — dataset variants)."""

from __future__ import annotations

from src import config
from src.usecase.sources.telemetry.runner import _make_processing


def test_default_processing_is_the_reference_treatment():
    cfg = _make_processing()  # defaults
    assert cfg.interpolate.get("flag") == config.TELEMETRY_INTERPOLATED_COLUMN  # coverage flag on
    assert cfg.outliers == []  # no winsorisation by default
    assert cfg.dedup["strategy"] == "mean" and cfg.normalize  # dedup + z-score kept


def test_nan_aware_variant_disables_interpolation():
    cfg = _make_processing(interpolate=False)
    assert cfg.interpolate == {}  # gaps left as NaN, no coverage flag


def test_clip_outliers_variant_enables_winsorisation():
    cfg = _make_processing(clip_outliers=True)
    assert set(cfg.outliers) == set(config.TELEMETRY_PARAM_COLUMNS) - {
        config.TELEMETRY_PIECES_COLUMN
    }
