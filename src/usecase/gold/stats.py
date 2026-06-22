"""Gold statistics (the OVERVIEW step): what the training table contains.

Works from the built ``gold.features`` DataFrame: feature counts by group, label positive
rates and censored (unusable) rows per horizon, and history-induced missingness.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import config
from src.framework.common.reporting import markdown_table
from src.usecase.gold.features import LABEL_H, WE, WS

_IDS = [config.MACHINE_COLUMN, WS, WE, "split_set"]
_LABELS = [f"label_failure_next_{lab}" for lab, _ in LABEL_H]


def feature_groups(df: pd.DataFrame) -> dict[str, list[str]]:
    """Classify columns into feature groups (identifiers, memory, trend, … labels)."""
    groups: dict[str, list[str]] = {
        "identifiers": [],
        "memory": [],
        "trend": [],
        "anomaly": [],
        "context_incidents": [],
        "context_signals": [],
        "context_maintenance": [],
        "labels": [],
    }
    for c in df.columns:
        if c in _IDS:
            groups["identifiers"].append(c)
        elif c.startswith("label_"):
            groups["labels"].append(c)
        elif "_trend_" in c:
            groups["trend"].append(c)
        elif c.endswith("_z_24h") or c.endswith("_z_machine"):
            groups["anomaly"].append(c)
        elif c.startswith("sig_"):
            groups["context_signals"].append(c)
        elif c.startswith("inc_"):
            groups["context_incidents"].append(c)
        elif c.startswith("mnt_"):
            groups["context_maintenance"].append(c)
        elif "_mean_" in c or "_max_" in c or "_std_" in c:
            groups["memory"].append(c)
    return groups


def summary_markdown(df: pd.DataFrame, spine_rows: int) -> str:
    """Recap: silver spine rows, gold rows, feature counts by group, full-row completeness."""
    groups = feature_groups(df)
    n_feat = sum(len(v) for k, v in groups.items() if k not in ("identifiers", "labels"))
    feat_cols = [c for k, v in groups.items() if k not in ("identifiers", "labels") for c in v]
    full = int(df[feat_cols].notna().all(axis=1).sum())
    lines = [
        f"- **Silver spine rows** (telemetry): {spine_rows}",
        f"- **Gold rows ingested**: {len(df)}",
        f"- **Total columns**: {df.shape[1]} — **features**: {n_feat}, "
        f"labels: {len(groups['labels'])}, identifiers: {len(groups['identifiers'])}",
        f"- **Rows with all features present** (no history-induced NaN): {full} "
        f"({100 * full / len(df):.1f}%)",
    ]
    rows = [[k, len(v)] for k, v in groups.items() if k not in ("identifiers", "labels")]
    return "\n".join(lines) + "\n\n" + markdown_table(["feature group", "count"], rows)


def label_markdown(df: pd.DataFrame) -> str:
    """Per-horizon: positives, negatives, censored (NaN = unusable) and positive rate."""
    headers = ["label", "positives", "negatives", "censored (unusable)", "positive rate"]
    rows = []
    for col in _LABELS:
        if col not in df.columns:
            continue
        s = df[col]
        pos = int((s == 1).sum())
        neg = int((s == 0).sum())
        cens = int(s.isna().sum())
        rate = f"{100 * pos / (pos + neg):.2f}%" if (pos + neg) else "—"
        rows.append([f"`{col}`", pos, neg, cens, rate])
    return markdown_table(headers, rows)


def plot_label_positive_rates(df: pd.DataFrame, output_dir: Path) -> Path:
    """Bar chart of the failure positive rate per horizon (among usable rows)."""
    out = Path(output_dir) / "gold_label_rates.png"
    labels, rates = [], []
    for col in _LABELS:
        if col not in df.columns:
            continue
        s = df[col]
        pos, tot = int((s == 1).sum()), int(s.notna().sum())
        labels.append(col.replace("label_failure_next_", ""))
        rates.append(100 * pos / tot if tot else 0.0)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, rates, color="#C44E52", edgecolor="white")
    ax.set_title("Failure positive rate per horizon")
    ax.set_xlabel("horizon")
    ax.set_ylabel("positive rate (%)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out
