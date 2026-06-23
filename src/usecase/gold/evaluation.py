"""Evaluation metrics for rare-event failure prediction (model-agnostic, dependency-free).

The pipeline produces the Gold dataset; the model is trained elsewhere. These helpers score a
model's predictions in a way suited to **strong class imbalance** (failures are ~1–7% of rows):
PR-AUC (average precision), recall at an alert budget (top-k%), precision/recall at a threshold,
and **lead time** (hours of warning before the failure). Evaluate on the held-out ``split_set``
and drop censored rows (NaN label). All functions take plain arrays / Series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _arrays(y_true, y_score) -> tuple[np.ndarray, np.ndarray]:
    return np.asarray(y_true, dtype=float), np.asarray(y_score, dtype=float)


def pr_auc(y_true, y_score) -> float:
    """Average precision (area under the precision-recall curve). NaN if no positives."""
    yt, ys = _arrays(y_true, y_score)
    order = np.argsort(-ys)
    yt = yt[order]
    positives = yt.sum()
    if positives == 0:
        return float("nan")
    tp = np.cumsum(yt)
    fp = np.cumsum(1 - yt)
    precision = tp / (tp + fp)
    recall = tp / positives
    recall_prev = np.concatenate([[0.0], recall[:-1]])
    return float(np.sum((recall - recall_prev) * precision))


def recall_at_top_k(y_true, y_score, k_frac: float = 0.01) -> float:
    """Recall captured by alerting on the top ``k_frac`` highest-scored rows (alert budget)."""
    yt, ys = _arrays(y_true, y_score)
    positives = yt.sum()
    if positives == 0:
        return float("nan")
    k = max(1, int(round(k_frac * len(yt))))
    top = np.argsort(-ys)[:k]
    return float(yt[top].sum() / positives)


def precision_recall_at_threshold(y_true, y_score, threshold: float = 0.5) -> dict:
    """Precision / recall / F1 / counts for a hard threshold on the score."""
    yt, ys = _arrays(y_true, y_score)
    pred = ys >= threshold
    pos = yt > 0
    tp = int(np.sum(pred & pos))
    fp = int(np.sum(pred & ~pos))
    fn = int(np.sum(~pred & pos))
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall and not (np.isnan(precision) or np.isnan(recall))
        else float("nan")
    )
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def lead_time_hours(ttf_hours, y_true, y_score, threshold: float = 0.5) -> dict:
    """Hours of warning at true-positive alerts: ``label_ttf_hours`` where the model fires early.

    Higher = more actionable. Uses the Gold ``label_ttf_hours`` (time to the next failure).
    """
    yt, ys = _arrays(y_true, y_score)
    ttf = np.asarray(ttf_hours, dtype=float)
    flagged = (ys >= threshold) & (yt > 0)
    lt = ttf[flagged]
    lt = lt[~np.isnan(lt)]
    if lt.size == 0:
        return {"n": 0, "median": float("nan"), "mean": float("nan")}
    return {"n": int(lt.size), "median": float(np.median(lt)), "mean": float(np.mean(lt))}


def evaluation_frame(gold: pd.DataFrame, label: str, split: str | None = "test") -> pd.DataFrame:
    """Rows usable to evaluate ``label``: the chosen ``split_set`` minus censored (NaN) labels."""
    sub = gold
    if split is not None and "split_set" in sub.columns:
        sub = sub[sub["split_set"] == split]
    return sub[sub[label].notna()]


def evaluate(y_true, y_score, ttf_hours=None, threshold: float = 0.5) -> dict:
    """Bundle the headline metrics for one (label, score) pair."""
    out = {
        "n": int(len(y_true)),
        "positive_rate": float(np.mean(np.asarray(y_true, dtype=float) > 0)),
        "pr_auc": pr_auc(y_true, y_score),
        "recall_at_top_1pct": recall_at_top_k(y_true, y_score, 0.01),
        "recall_at_top_5pct": recall_at_top_k(y_true, y_score, 0.05),
        **{
            f"thr_{k}": v
            for k, v in precision_recall_at_threshold(y_true, y_score, threshold).items()
        },
    }
    if ttf_hours is not None:
        out["lead_time"] = lead_time_hours(ttf_hours, y_true, y_score, threshold)
    return out
