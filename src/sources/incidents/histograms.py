"""Histograms of incident counts: by machine, operator, signal and confidence."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt

from src import config

logger = logging.getLogger(__name__)


def plot_incidents_per_machine(df, output_dir: Path) -> Path:
    """Number of incidents per machine (bar chart)."""
    out = Path(output_dir) / "2.1_hist_incidents_machine.png"
    counts = df[config.MACHINE_COLUMN].value_counts().sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(counts.index.astype(str), counts.values, color="#4C72B0")
    ax.set_title("Number of incidents per machine")
    ax.set_xlabel("Machine")
    ax.set_ylabel("Number of incidents")
    ax.tick_params(axis="x", rotation=90)
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, out)
    return out


def plot_incidents_per_operator(df, output_dir: Path) -> Path:
    """Number of incidents per operator (pseudonymised id, bar chart)."""
    out = Path(output_dir) / "2.2_hist_incidents_operator.png"
    counts = df["operator_name"].value_counts().sort_values(ascending=False)
    labels = [str(op)[:8] for op in counts.index]  # short pseudonym

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(labels, counts.values, color="#55A868")
    ax.set_title("Number of incidents per operator (pseudonymised)")
    ax.set_xlabel("Operator (pseudonymised)")
    ax.set_ylabel("Number of incidents")
    ax.tick_params(axis="x", rotation=90)
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, out)
    return out


def plot_incidents_per_signal(df, output_dir: Path) -> Path:
    """Number of incidents per signal (the ``type_`` columns, bar chart)."""
    out = Path(output_dir) / "2.3_hist_incidents_signal.png"
    present_signals = [c for c in config.SIGNAL_COLUMNS if c in df.columns]
    counts = df[present_signals].fillna(0).astype(int).sum().sort_values(ascending=False)
    labels = [s.replace("type_", "") for s in counts.index]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(labels, counts.values, color="#C44E52")
    ax.set_title("Number of incidents per signal")
    ax.set_xlabel("Signal")
    ax.set_ylabel("Number of incidents")
    ax.tick_params(axis="x", rotation=90)
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, out)
    return out


def plot_incidents_per_confidence(df, output_dir: Path) -> Path:
    """Distribution of incidents by reporting confidence index (histogram)."""
    out = Path(output_dir) / "2.4_hist_incidents_confidence.png"
    present_signals = [c for c in config.SIGNAL_COLUMNS if c in df.columns]

    fig, ax = plt.subplots(figsize=(10, 5))
    if config.CONFIDENCE_COLUMN in df.columns:
        ax.hist(
            df[config.CONFIDENCE_COLUMN].dropna(),
            bins=len(present_signals) + 1,
            color="#8172B3",
            edgecolor="white",
        )
    ax.set_title("Number of incidents by confidence index")
    ax.set_xlabel("Confidence index (active signals / total)")
    ax.set_ylabel("Number of incidents")
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, out)
    return out


def plot_all(df, output_dir: Path) -> list[Path]:
    """Produce the four incident histograms and return their paths."""
    return [
        plot_incidents_per_machine(df, output_dir),
        plot_incidents_per_operator(df, output_dir),
        plot_incidents_per_signal(df, output_dir),
        plot_incidents_per_confidence(df, output_dir),
    ]


def _save(fig, out: Path) -> None:
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
