"""Unit tests for the Silver reject policy (``split_rejected``)."""

from __future__ import annotations

import pandas as pd

from src.ingestion.validate import PARSE_OK, PARSE_REASON
from src.silver.refine import split_rejected


def _frame():
    return pd.DataFrame(
        {
            "v": [1, 2, 3, 4, 5, 6],
            PARSE_OK: [True, False, False, False, False, False],
            PARSE_REASON: [
                "",  # clean            -> kept
                "duplicate",  # correctable      -> kept
                "missing:severity",  # correctable      -> kept
                "type:severity",  # not correctable  -> rejected
                "domain:shift",  # not correctable  -> rejected
                "duplicate;type:x",  # mixed (one bad) -> rejected
            ],
        }
    )


def test_split_keeps_clean_and_correctable_rows():
    kept, rejected = split_rejected(_frame())
    assert kept["v"].tolist() == [1, 2, 3]
    assert rejected["v"].tolist() == [4, 5, 6]


def test_kept_frame_drops_parse_columns():
    kept, _ = split_rejected(_frame())
    assert PARSE_OK not in kept.columns
    assert PARSE_REASON not in kept.columns


def test_rejected_frame_retains_reasons():
    _, rejected = split_rejected(_frame())
    assert PARSE_REASON in rejected.columns
    assert "type:severity" in rejected[PARSE_REASON].tolist()


def test_no_parse_columns_means_keep_all():
    df = pd.DataFrame({"v": [1, 2, 3]})
    kept, rejected = split_rejected(df)
    assert len(kept) == 3 and len(rejected) == 0
