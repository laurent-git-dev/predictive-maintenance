"""Telemetry boxplots: distribution of each parameter, per machine."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt

from src import config

logger = logging.getLogger(__name__)

# Ordered prefix per parameter, so output files stay sorted.
_PARAM_PREFIX = {param: f"1.{i}" for i, param in enumerate(config.TELEMETRY_PARAM_COLUMNS, start=1)}


def plot_param_by_machine(df, param: str, output_dir: Path) -> Path:
    """Boxplot of a single parameter per machine (one figure)."""
    out = Path(output_dir) / f"{_PARAM_PREFIX[param]}_box_{param}.png"
    machines = sorted(df[config.MACHINE_COLUMN].dropna().unique())
    data = [df.loc[df[config.MACHINE_COLUMN] == m, param].dropna().values for m in machines]

    fig, ax = plt.subplots(figsize=(max(8, 0.6 * len(machines) + 2), 6))
    ax.boxplot(data, tick_labels=[str(m) for m in machines], showfliers=False)
    ax.set_title(f"{param} by machine")
    ax.set_xlabel("Machine")
    ax.set_ylabel(param)
    ax.tick_params(axis="x", rotation=90)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_all(df, output_dir: Path) -> list[Path]:
    """Produce one boxplot-by-machine figure per telemetry parameter."""
    return [
        plot_param_by_machine(df, param, output_dir)
        for param in config.TELEMETRY_PARAM_COLUMNS
        if param in df.columns
    ]
