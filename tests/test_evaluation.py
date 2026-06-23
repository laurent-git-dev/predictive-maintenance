"""Unit tests for the rare-event evaluation metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.usecase.gold.evaluation import (
    evaluation_frame,
    lead_time_hours,
    pr_auc,
    precision_recall_at_threshold,
    recall_at_top_k,
)


def test_pr_auc_perfect_and_degenerate():
    # Perfect ranking (all positives scored above negatives) -> AP = 1.
    assert pr_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    # No positives -> undefined.
    assert np.isnan(pr_auc([0, 0, 0], [0.1, 0.2, 0.3]))


def test_recall_at_top_k_budget():
    y = [0, 0, 0, 1, 1]  # 2 positives
    s = [0.1, 0.2, 0.3, 0.9, 0.95]  # both positives are the top-2
    assert recall_at_top_k(y, s, k_frac=0.4) == 1.0  # top 40% of 5 = 2 rows -> both positives
    assert recall_at_top_k(y, s, k_frac=0.2) == 0.5  # top 1 row -> 1 of 2 positives


def test_precision_recall_at_threshold():
    m = precision_recall_at_threshold([0, 1, 1, 0], [0.1, 0.9, 0.4, 0.8], threshold=0.5)
    assert m["tp"] == 1 and m["fp"] == 1 and m["fn"] == 1
    assert m["precision"] == 0.5 and m["recall"] == 0.5


def test_lead_time_uses_ttf_at_true_positive_alerts():
    # rows: flagged (score>=.5) AND true positive -> their ttf contributes
    lt = lead_time_hours(
        ttf_hours=[10, 4, np.nan, 20],
        y_true=[1, 1, 1, 0],
        y_score=[0.9, 0.6, 0.2, 0.7],
        threshold=0.5,
    )
    assert lt["n"] == 2 and lt["median"] == 7.0  # ttf 10 and 4 (row3 below thr; row4 not positive)


def test_evaluation_frame_drops_censored_and_filters_split():
    gold = pd.DataFrame(
        {
            "split_set": ["train", "test", "test", "test"],
            "label_failure_next_6h": [1, 0, 1, np.nan],
        }
    )
    out = evaluation_frame(gold, "label_failure_next_6h", split="test")
    assert len(out) == 2  # test rows minus the censored (NaN) one
