"""Histograms per signal and per machine, with the reporting confidence index."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import config

logger = logging.getLogger(__name__)


def plot_signals_by_machine(df, output_dir: Path) -> Path:
    """Produce a combined signal / machine / confidence-index figure.

    The figure has three panels:

    1. Total frequency of each signal.
    2. Heatmap (machine x signal) of the number of activations.
    3. Distribution of the reporting confidence index.
    """
    out = Path(output_dir) / "hist_signals_machine.png"
    present_signals = [c for c in config.SIGNAL_COLUMNS if c in df.columns]

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    # ── Panel 1: frequency per signal ────────────────────────────────────────
    totals = df[present_signals].fillna(0).astype(int).sum().sort_values()
    axes[0].barh(
        [s.replace("type_", "") for s in totals.index],
        totals.values,
        color="#4C72B0",
    )
    axes[0].set_title("Frequency per signal")
    axes[0].set_xlabel("Number of activations")
    axes[0].grid(True, axis="x", alpha=0.3)

    # ── Panel 2: machine x signal heatmap ────────────────────────────────────
    if config.MACHINE_COLUMN in df.columns:
        pivot = (
            df.assign(**{c: df[c].fillna(0).astype(int) for c in present_signals})
            .groupby(config.MACHINE_COLUMN)[present_signals]
            .sum()
        )
        im = axes[1].imshow(pivot.values, aspect="auto", cmap="YlOrRd")
        axes[1].set_xticks(range(len(present_signals)))
        axes[1].set_xticklabels([s.replace("type_", "") for s in present_signals], rotation=90)
        axes[1].set_yticks(range(len(pivot.index)))
        axes[1].set_yticklabels(pivot.index.astype(str))
        axes[1].set_title("Activations per machine and signal")
        fig.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    else:
        axes[1].set_visible(False)

    # ── Panel 3: confidence index ────────────────────────────────────────────
    if config.CONFIDENCE_COLUMN in df.columns:
        axes[2].hist(
            df[config.CONFIDENCE_COLUMN].dropna(),
            bins=len(present_signals) + 1,
            color="#55A868",
            edgecolor="white",
        )
        axes[2].set_title("Reporting confidence index")
        axes[2].set_xlabel("Index (active signals / total)")
        axes[2].set_ylabel("Number of incidents")
        axes[2].grid(True, axis="y", alpha=0.3)
    else:
        axes[2].set_visible(False)

    fig.suptitle("Signal analysis per machine", fontsize=14)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out
