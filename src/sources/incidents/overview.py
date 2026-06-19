"""Source-level overview plots for incidents (global analysis, used by the notebook).

These complement the per-feature understanding with a whole-source view:
- the incident volume over time (chronogram);
- the incident count per activated signal (``type_*`` flags).
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import config

logger = logging.getLogger(__name__)


def plots(df: pd.DataFrame, output_dir: Path) -> list[Path]:
    """Produce every whole-source overview plot (used by the notebook overview hook)."""
    return [
        plot_incidents_over_time(df, output_dir),
        plot_incidents_by_signal(df, output_dir),
    ]


def plot_incidents_over_time(
    df: pd.DataFrame,
    output_dir: Path,
    date_col: str = config.DATE_COLUMN,
    freq: str = "W",
    count_label: str = "incidents",
) -> Path:
    """Line chart of the incident volume over time (chronogram).

    Counts are resampled at ``freq`` (default weekly), keeping empty periods at 0 so
    the timeline stays continuous. File ``overview_1_<count_label>_over_time.png``.
    """
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    series = pd.Series(1, index=pd.DatetimeIndex(dates)).resample(freq).sum()
    out = Path(output_dir) / f"overview_1_{count_label}_over_time.png"

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(series.index, series.to_numpy(), color="#4C72B0", linewidth=1.8)
    ax.fill_between(series.index, series.to_numpy(), alpha=0.2, color="#4C72B0")
    ax.set_title(f"{count_label.capitalize()} over time (resampled '{freq}')")
    ax.set_xlabel(date_col)
    ax.set_ylabel(f"Number of {count_label}")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_incidents_by_signal(
    df: pd.DataFrame,
    output_dir: Path,
    signal_cols: tuple[str, ...] = config.SIGNAL_COLUMNS,
    count_label: str = "incidents",
) -> Path:
    """Bar chart of the incident count where each signal is active (descending).

    An incident may activate several signals, so totals can exceed the number of
    incidents. File ``overview_2_<count_label>_by_signal.png``.
    """
    present = [c for c in signal_cols if c in df.columns]
    counts = {
        c: int(pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int).eq(1).sum())
        for c in present
    }
    counts = dict(sorted(counts.items(), key=lambda kv: kv[1]))  # ascending → largest on top
    labels = [c.removeprefix("type_") for c in counts]
    out = Path(output_dir) / f"overview_2_{count_label}_by_signal.png"

    fig, ax = plt.subplots(figsize=(10, max(5, 0.5 * len(counts) + 2)))
    bars = ax.barh(labels, list(counts.values()), color="#4C72B0", edgecolor="white")
    ax.bar_label(bars, padding=3)
    ax.set_title(f"{count_label.capitalize()} by activated signal")
    ax.set_xlabel(f"Number of {count_label}")
    ax.set_ylabel("signal")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out
