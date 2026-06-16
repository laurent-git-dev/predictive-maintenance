"""Correlation graphs: severity vs signals, and severity vs comment presence."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import config

logger = logging.getLogger(__name__)


def plot_severity_signals_correlation(df, output_dir: Path) -> Path:
    """Correlation matrix between severity and the ``type_`` signals."""
    out = Path(output_dir) / "3.1_corr_severity_signals.png"
    present_signals = [c for c in config.SIGNAL_COLUMNS if c in df.columns]

    cols = list(present_signals)
    if config.SEVERITY_COLUMN in df.columns:
        cols.append(config.SEVERITY_COLUMN)

    matrix = df[cols].apply(pd.to_numeric, errors="coerce").corr()
    labels = [c.replace("type_", "") for c in matrix.columns]

    fig, ax = plt.subplots(figsize=(10, 9))
    im = ax.imshow(matrix.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=90)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)

    for i in range(len(labels)):
        for j in range(len(labels)):
            val = matrix.values[i, j]
            if pd.notna(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", color="black", fontsize=7)

    ax.set_title("Correlation matrix — severity / signals")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_severity_comment_correlation(df, output_dir: Path) -> Path:
    """Relationship between severity and the presence of a comment.

    A comment is free text, so it is reduced to its **presence** (the
    ``comment_pii_flag`` column). The chart shows the share of incidents that
    carry a comment for each severity level, and the point-biserial correlation
    between severity and comment presence is reported in the title.
    """
    out = Path(output_dir) / "3.2_corr_severity_comment.png"

    severity = pd.to_numeric(df[config.SEVERITY_COLUMN], errors="coerce")
    if "comment_pii_flag" in df.columns:
        has_comment = df["comment_pii_flag"].astype(float)
    else:  # fallback if the flag is missing
        has_comment = df[config.COMMENT_COLUMN].notna().astype(float)

    valid = severity.notna() & has_comment.notna()
    corr = severity[valid].corr(has_comment[valid])
    share = has_comment.groupby(severity).mean().sort_index()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(share.index.astype(str), share.values, color="#937860")
    ax.set_ylim(0, 1)
    ax.set_title(f"Share of incidents with a comment, by severity (corr = {corr:.2f})")
    ax.set_xlabel("Severity")
    ax.set_ylabel("Share with a comment")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_all(df, output_dir: Path) -> list[Path]:
    """Produce the two correlation graphs and return their paths."""
    return [
        plot_severity_signals_correlation(df, output_dir),
        plot_severity_comment_correlation(df, output_dir),
    ]
