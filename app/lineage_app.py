"""Streamlit app to visualise the pipeline lineage (``meta.processing_runs``).

Run from the project root:  ``uv run streamlit run app/lineage_app.py``
Reuses the lineage helpers (no business logic here): a per-batch overview, a rows
ingested/rejected chart, and the steps of a selected batch.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.framework.db.engine import get_engine, is_available  # noqa: E402
from src.framework.lineage.dashboard import summarize_batches  # noqa: E402
from src.framework.lineage.tracker import read_all_runs  # noqa: E402

st.set_page_config(page_title="Lineage — Predictive Maintenance", layout="wide")
st.title("🔎 Pipeline lineage — meta.processing_runs")

_STEP_COLS = [
    "step",
    "layer",
    "source",
    "status",
    "rows_read",
    "rows_ingested",
    "rows_rejected",
    "quality_ok",
    "duration_s",
    "code_version",
    "output_hash",
]


@st.cache_data(ttl=30)
def _load_runs() -> pd.DataFrame:
    """All lineage rows from the DB (empty if PostgreSQL is unreachable)."""
    if not is_available():
        return pd.DataFrame()
    return read_all_runs(get_engine())


if st.sidebar.button("🔄 Refresh"):
    _load_runs.clear()

runs = _load_runs()

if runs.empty:
    st.warning(
        "No lineage to show. Start PostgreSQL (`docker compose up -d`) and run the pipeline "
        "(`uv run python scripts/predmaint.py run`), then refresh."
    )
    st.stop()

summary = summarize_batches(runs)

col1, col2, col3 = st.columns(3)
col1.metric("Batches", len(summary))
col2.metric("Steps (total)", int(summary["steps"].sum()))
col3.metric("Last batch quality", "OK" if bool(summary.iloc[0]["quality_ok"]) else "NOK")

st.subheader("Batches (newest first)")
st.dataframe(summary, use_container_width=True, hide_index=True)

st.subheader("Rows ingested vs rejected per batch")
st.bar_chart(summary.set_index("batch_id")[["rows_ingested", "rows_rejected"]].sort_index())

st.subheader("Steps of a batch")
batch = st.selectbox("Batch", summary["batch_id"].tolist())
steps = runs[runs["batch_id"] == batch].sort_values("started_at")
st.dataframe(
    steps[[c for c in _STEP_COLS if c in steps.columns]],
    use_container_width=True,
    hide_index=True,
)
