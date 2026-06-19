"""Source-level overview plots for telemetry (global analysis, used by the notebook)."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import config

logger = logging.getLogger(__name__)

# Physical sensor measures shown on the overview (pieces_produced has its own series).
_OVERVIEW_MEASURES: tuple[str, ...] = (
    "temperature_c",
    "pressure_bar",
    "voltage_mean_v",
    "rotation_mean_rpm",
)


def plots(df: pd.DataFrame, output_dir: Path) -> list[Path]:
    """Produce every whole-source overview plot (used by the notebook overview hook)."""
    return [plot_measures_over_time(df, output_dir)]


def plot_measures_over_time(
    df: pd.DataFrame,
    output_dir: Path,
    measures: tuple[str, ...] = _OVERVIEW_MEASURES,
    time_col: str = config.TELEMETRY_TIMESTAMP_COLUMN,
    freq: str = "D",
) -> Path:
    """One stacked subplot per measure: its mean over time across all machines.

    Measures are drawn on separate axes (very different scales). Values are resampled at
    ``freq`` (default daily). File ``overview_1_measures_over_time.png``.
    """
    out = Path(output_dir) / "overview_1_measures_over_time.png"
    data = df.copy()
    data[time_col] = pd.to_datetime(data[time_col], errors="coerce")
    data = data.dropna(subset=[time_col]).set_index(time_col)
    present = [m for m in measures if m in data.columns]

    fig, axes = plt.subplots(len(present), 1, figsize=(12, 2.6 * len(present)), sharex=True)
    axes = [axes] if len(present) == 1 else list(axes)
    for ax, measure in zip(axes, present, strict=True):
        series = data[measure].resample(freq).mean()
        ax.plot(series.index, series.to_numpy(), color="#4C72B0", linewidth=1.2)
        ax.set_ylabel(measure)
        ax.grid(True, alpha=0.3)
    axes[0].set_title(f"Telemetry measures over time (mean per '{freq}', all machines)")
    axes[-1].set_xlabel(time_col)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out
