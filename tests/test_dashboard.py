"""Unit tests for the lineage dashboard aggregation (synthetic runs, no DB)."""

from __future__ import annotations

import pandas as pd

from src.framework.lineage.dashboard import dashboard_markdown, summarize_batches


def _runs():
    return pd.DataFrame(
        [
            {
                "batch_id": "B1",
                "step": "ingest",
                "started_at": pd.Timestamp("2026-01-01 10:00"),
                "rows_ingested": 100,
                "rows_rejected": 2,
                "quality_ok": True,
                "status": "success",
                "duration_s": 1.0,
                "code_version": "aaa",
            },
            {
                "batch_id": "B1",
                "step": "refine",
                "started_at": pd.Timestamp("2026-01-01 10:01"),
                "rows_ingested": 98,
                "rows_rejected": 0,
                "quality_ok": True,
                "status": "success",
                "duration_s": 2.0,
                "code_version": "aaa",
            },
            {
                "batch_id": "B2",
                "step": "ingest",
                "started_at": pd.Timestamp("2026-01-02 10:00"),
                "rows_ingested": 50,
                "rows_rejected": 5,
                "quality_ok": False,
                "status": "failed",
                "duration_s": 3.0,
                "code_version": "bbb",
            },
        ]
    )


def test_summarize_batches_aggregates_per_batch_newest_first():
    summary = summarize_batches(_runs()).set_index("batch_id")
    assert list(summarize_batches(_runs())["batch_id"]) == ["B2", "B1"]  # newest first
    assert summary.loc["B1", "steps"] == 2
    assert summary.loc["B1", "rows_ingested"] == 198
    assert summary.loc["B1", "rows_rejected"] == 2
    assert bool(summary.loc["B1", "quality_ok"]) is True
    assert summary.loc["B1", "failed_steps"] == 0
    assert bool(summary.loc["B2", "quality_ok"]) is False
    assert summary.loc["B2", "failed_steps"] == 1


def test_dashboard_markdown_renders_and_handles_empty():
    md = dashboard_markdown(_runs())
    assert "| batch |" in md and "B2" in md and "NOK" in md and "OK" in md
    assert dashboard_markdown(pd.DataFrame()) == "_No batch recorded yet._"
