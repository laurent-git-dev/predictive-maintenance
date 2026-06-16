"""Temporal distribution plots of incidents (day / week / shift)."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt

from src import config

logger = logging.getLogger(__name__)


def plot_incidents_per_day(df, output_dir: Path) -> Path:
    """Plot the number of incidents per day and save it as PNG."""
    out = Path(output_dir) / "dist_incidents_day.png"
    series = df.dropna(subset=[config.DATE_COLUMN]).groupby(config.DATE_COLUMN).size()

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(series.index, series.values, marker=".", linewidth=1)
    ax.set_title("Incident distribution per day")
    ax.set_xlabel("Date")
    ax.set_ylabel("Number of incidents")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    _save(fig, out)
    return out


def plot_incidents_per_week(df, output_dir: Path) -> Path:
    """Plot the number of incidents per week (weekly resampling)."""
    out = Path(output_dir) / "dist_incidents_week.png"
    series = (
        df.dropna(subset=[config.DATE_COLUMN]).set_index(config.DATE_COLUMN).resample("W").size()
    )

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(series.index, series.values, width=5)
    ax.set_title("Incident distribution per week")
    ax.set_xlabel("Week")
    ax.set_ylabel("Number of incidents")
    ax.grid(True, axis="y", alpha=0.3)
    fig.autofmt_xdate()
    _save(fig, out)
    return out


def plot_incidents_per_shift(df, output_dir: Path) -> Path:
    """Plot the number of incidents per shift (morning / afternoon / night)."""
    out = Path(output_dir) / "dist_incidents_shift.png"
    counts = df[config.SHIFT_COLUMN].value_counts()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(counts.index.astype(str), counts.values, color="#4C72B0")
    ax.set_title("Incident distribution per shift")
    ax.set_xlabel("Shift")
    ax.set_ylabel("Number of incidents")
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, out)
    return out


def plot_all(df, output_dir: Path) -> list[Path]:
    """Produce the three distribution plots and return their paths."""
    return [
        plot_incidents_per_day(df, output_dir),
        plot_incidents_per_week(df, output_dir),
        plot_incidents_per_shift(df, output_dir),
    ]


def _save(fig, out: Path) -> None:
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
