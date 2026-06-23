"""Lineage dashboard: aggregate ``meta.processing_runs`` into a per-batch overview.

Turns the raw step rows (one per layer/source) into a batch-level summary (steps, rows
ingested/rejected, quality, duration, code version) plus a markdown table and a plot — a small
observability view over the investment in lineage tracking.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.framework.common.reporting import markdown_table
from src.framework.lineage.tracker import read_all_runs


def summarize_batches(runs: pd.DataFrame) -> pd.DataFrame:
    """Aggregate step-level runs into one row per ``batch_id`` (most recent first)."""
    if runs.empty:
        return pd.DataFrame()
    agg = (
        runs.groupby("batch_id")
        .agg(
            started_at=("started_at", "min"),
            steps=("step", "size"),
            rows_ingested=("rows_ingested", "sum"),
            rows_rejected=("rows_rejected", "sum"),
            quality_ok=("quality_ok", "min"),  # False if any step failed quality
            failed_steps=("status", lambda s: int((s == "failed").sum())),
            duration_s=("duration_s", "sum"),
            code_version=("code_version", "first"),
        )
        .reset_index()
        .sort_values("started_at", ascending=False)
    )
    return agg


def dashboard_markdown(runs: pd.DataFrame) -> str:
    """Per-batch summary as a markdown table (newest first)."""
    summary = summarize_batches(runs)
    if summary.empty:
        return "_No batch recorded yet._"
    headers = [
        "batch",
        "started",
        "steps",
        "rows in",
        "rows rejected",
        "quality",
        "failed",
        "duration (s)",
        "code",
    ]
    rows = [
        [
            r["batch_id"],
            str(r["started_at"]),
            int(r["steps"]),
            int(r["rows_ingested"] or 0),
            int(r["rows_rejected"] or 0),
            "OK" if bool(r["quality_ok"]) else "NOK",
            int(r["failed_steps"]),
            round(float(r["duration_s"] or 0), 1),
            r["code_version"],
        ]
        for _, r in summary.iterrows()
    ]
    return markdown_table(headers, rows)


def plot_batches(runs: pd.DataFrame, output_dir: Path) -> Path | None:
    """Bar chart of rows ingested vs rejected per batch (chronological). ``None`` if empty."""
    summary = summarize_batches(runs).sort_values("started_at")
    if summary.empty:
        return None
    out = Path(output_dir) / "lineage_batches.png"
    labels = summary["batch_id"].astype(str).tolist()
    x = range(len(labels))
    fig, ax = plt.subplots(figsize=(max(6, 1.2 * len(labels)), 4))
    ax.bar(x, summary["rows_ingested"].fillna(0), color="#4C72B0", label="ingested")
    ax.bar(x, summary["rows_rejected"].fillna(0), color="#C44E52", label="rejected")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_title("Rows ingested vs rejected per batch")
    ax.set_ylabel("rows")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def lineage_dashboard_markdown(engine) -> str:
    """Read every batch from the database and render the dashboard markdown."""
    return dashboard_markdown(read_all_runs(engine))
