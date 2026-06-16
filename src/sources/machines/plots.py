"""Maintenance plots: count per machine, duration, type split, component frequency."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import config

logger = logging.getLogger(__name__)


def plot_maintenance_per_machine(df, output_dir: Path) -> Path:
    """Number of maintenance events per machine (bar chart)."""
    out = Path(output_dir) / "1.1_hist_maintenance_machine.png"
    counts = df[config.MACHINE_COLUMN].value_counts().sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(counts.index.astype(str), counts.values, color="#4C72B0")
    ax.set_title("Number of maintenance events per machine")
    ax.set_xlabel("Machine")
    ax.set_ylabel("Number of maintenance events")
    ax.tick_params(axis="x", rotation=90)
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, out)
    return out


def plot_duration_per_machine(df, output_dir: Path) -> Path:
    """Distribution of maintenance duration per machine (boxplot)."""
    out = Path(output_dir) / "1.2_box_duration_machine.png"
    machines = sorted(df[config.MACHINE_COLUMN].dropna().unique())
    data = [
        df.loc[df[config.MACHINE_COLUMN] == m, config.MAINTENANCE_DURATION_COLUMN].dropna().values
        for m in machines
    ]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.boxplot(data, tick_labels=[str(m) for m in machines], showfliers=False)
    ax.set_title("Maintenance duration by machine")
    ax.set_xlabel("Machine")
    ax.set_ylabel("Duration (hours)")
    ax.tick_params(axis="x", rotation=90)
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, out)
    return out


def plot_type_split(df, output_dir: Path) -> Path:
    """Proactive vs reactive maintenance, per machine (stacked bar)."""
    out = Path(output_dir) / "1.3_maintenance_type_split.png"
    pivot = pd.crosstab(df[config.MACHINE_COLUMN], df[config.MAINTENANCE_TYPE_COLUMN]).sort_index()

    fig, ax = plt.subplots(figsize=(12, 5))
    bottom = None
    colors = {"proactive": "#55A868", "reactive": "#C44E52"}
    for col in pivot.columns:
        ax.bar(
            pivot.index.astype(str),
            pivot[col].values,
            bottom=bottom,
            label=col,
            color=colors.get(col),
        )
        bottom = pivot[col].values if bottom is None else bottom + pivot[col].values
    ax.set_title("Maintenance type per machine (proactive vs reactive)")
    ax.set_xlabel("Machine")
    ax.set_ylabel("Number of maintenance events")
    ax.tick_params(axis="x", rotation=90)
    ax.legend(title="type")
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, out)
    return out


def plot_component_frequency(df, output_dir: Path) -> Path:
    """Number of maintenance events per component (bar chart)."""
    out = Path(output_dir) / "1.4_hist_maintenance_component.png"
    counts = df[config.MAINTENANCE_COMPONENT_COLUMN].value_counts().sort_values()

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(counts.index.astype(str), counts.values, color="#8172B3")
    ax.set_title("Maintenance events per component")
    ax.set_xlabel("Number of maintenance events")
    ax.grid(True, axis="x", alpha=0.3)
    _save(fig, out)
    return out


def plot_all(df, output_dir: Path) -> list[Path]:
    """Produce the four maintenance plots and return their paths."""
    return [
        plot_maintenance_per_machine(df, output_dir),
        plot_duration_per_machine(df, output_dir),
        plot_type_split(df, output_dir),
        plot_component_frequency(df, output_dir),
    ]


def _save(fig, out: Path) -> None:
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
