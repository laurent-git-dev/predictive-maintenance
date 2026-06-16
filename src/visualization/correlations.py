"""Correlation matrix between incident signals (and severity)."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import config

logger = logging.getLogger(__name__)


def plot_correlation_matrix(df, output_dir: Path) -> Path:
    """Plot the signal correlation matrix and save it as PNG.

    Severity is included if it is numeric, to visualise which signals are most
    related to incident severity.
    """
    out = Path(output_dir) / "corr_incidents_signals.png"
    present_signals = [c for c in config.SIGNAL_COLUMNS if c in df.columns]

    cols = list(present_signals)
    if config.SEVERITY_COLUMN in df.columns:
        severity_num = pd.to_numeric(df[config.SEVERITY_COLUMN], errors="coerce")
        if severity_num.notna().any():
            df = df.assign(**{config.SEVERITY_COLUMN: severity_num})
            cols.append(config.SEVERITY_COLUMN)

    matrix = df[cols].apply(pd.to_numeric, errors="coerce").corr()
    labels = [c.replace("type_", "") for c in matrix.columns]

    fig, ax = plt.subplots(figsize=(10, 9))
    im = ax.imshow(matrix.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=90)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)

    # Annotate coefficients for readability.
    for i in range(len(labels)):
        for j in range(len(labels)):
            val = matrix.values[i, j]
            if pd.notna(val):
                ax.text(
                    j,
                    i,
                    f"{val:.2f}",
                    ha="center",
                    va="center",
                    color="black",
                    fontsize=7,
                )

    ax.set_title("Incident / signal correlation matrix")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out
