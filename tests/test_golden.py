"""Golden (characterisation) tests: freeze row counts and content hashes per layer.

These run the in-memory path (source loaders -> ``to_silver`` -> Gold builder), so they need
``data/raw/`` but **no database**. They guard against accidental behaviour changes: if a value
legitimately changes, update the constants below. Skipped when the raw files are absent.
"""

from __future__ import annotations

import pytest

from src import config
from src.framework.lineage.tracker import _hash_df
from src.usecase.gold.features import build_gold_features
from src.usecase.sources.registry import SOURCE_SPECS

_RAW = [config.DEFAULT_INPUT_CSV, config.DEFAULT_TELEMETRY_CSV, config.DEFAULT_MACHINES_SQL]
pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in _RAW), reason="data/raw/* absent (golden tests need the sources)"
)

_SPECS = {s.name: s for s in SOURCE_SPECS}

# --- Frozen reference values (reference run) ---
BRONZE_ROWS = {"incidents": 1245, "telemetry": 135626, "machine": 15, "machines": 1562}
SILVER_ROWS = {"incidents": 1245, "telemetry": 134280, "maintenance": 1562}
SILVER_HASH = {"telemetry": "28e8bdfa1384a68c", "maintenance": "c3de808ca7e364ac"}
GOLD_ROWS, GOLD_COLS, GOLD_HASH = 134280, 216, "69fbf826237bb18d"


@pytest.fixture(scope="module")
def bronze():
    return {name: _SPECS[name].load_bronze() for name in BRONZE_ROWS}


@pytest.fixture(scope="module")
def silver(bronze):
    return {
        "incidents": _SPECS["incidents"].to_silver(bronze["incidents"])[0],
        "telemetry": _SPECS["telemetry"].to_silver(bronze["telemetry"])[0],
        "maintenance": _SPECS["machines"].to_silver(bronze["machines"])[0],
    }


@pytest.mark.golden
@pytest.mark.parametrize("name,expected", BRONZE_ROWS.items())
def test_bronze_row_counts(bronze, name, expected):
    assert len(bronze[name]) == expected


@pytest.mark.golden
@pytest.mark.parametrize("name,expected", SILVER_ROWS.items())
def test_silver_row_counts(silver, name, expected):
    assert len(silver[name]) == expected


@pytest.mark.golden
@pytest.mark.parametrize("name,expected", SILVER_HASH.items())
def test_silver_content_hash(silver, name, expected):
    # incidents is intentionally excluded: operator pseudonymisation is salt-dependent.
    assert _hash_df(silver[name]) == expected


@pytest.mark.golden
def test_gold_shape_and_hash(silver):
    gold = build_gold_features(silver)
    assert len(gold) == GOLD_ROWS
    assert gold.shape[1] == GOLD_COLS
    assert _hash_df(gold) == GOLD_HASH
