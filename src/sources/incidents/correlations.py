"""Correlation graphs: severity vs signals, and severity vs comment category."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import chi2_contingency

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


def severity_comment_association(df) -> dict:
    """Test the association between the comment category and severity.

    The comment is treated as a categorical variable (its distinct text values).
    Runs a chi-square test of independence and computes Cramer's V.

    Returns
    -------
    dict
        ``table`` (contingency DataFrame), ``chi2``, ``p_value``, ``dof``,
        ``cramers_v`` and a qualitative ``verdict``.
    """
    comment = df[config.COMMENT_COLUMN].astype("string").str.strip()
    mask = comment.notna() & comment.ne("")
    table = pd.crosstab(comment[mask], df.loc[mask, config.SEVERITY_COLUMN])
    table = table.loc[table.sum(axis=1).sort_values(ascending=False).index]

    chi2, p_value, dof, _ = chi2_contingency(table.values)
    n = table.values.sum()
    r, k = table.shape
    denom = n * min(r - 1, k - 1)
    v = float((chi2 / denom) ** 0.5) if denom > 0 else float("nan")

    if v < 0.1:
        strength = "negligible"
    elif v < 0.2:
        strength = "weak"
    elif v < 0.4:
        strength = "moderate"
    else:
        strength = "strong"
    significant = p_value < 0.05
    verdict = f"{strength}, {'significant' if significant else 'not significant'}"

    return {
        "table": table,
        "chi2": float(chi2),
        "p_value": float(p_value),
        "dof": int(dof),
        "cramers_v": v,
        "verdict": verdict,
    }


def plot_severity_comment_correlation(df, output_dir: Path) -> Path:
    """Heatmap of severity by comment category, with chi-square test + Cramer's V.

    Answers: does a given comment map to a consistent severity? Each row (comment)
    is normalised to show its severity profile; the title reports Cramer's V and
    the chi-square p-value (association significant or not).
    """
    out = Path(output_dir) / "3.2_corr_severity_comment.png"
    res = severity_comment_association(df)
    table = res["table"]
    proportions = table.div(table.sum(axis=1), axis=0)  # row-normalised

    fig, ax = plt.subplots(figsize=(9, max(4, 0.5 * len(table) + 2)))
    im = ax.imshow(proportions.values, cmap="YlOrRd", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(table.shape[1]))
    ax.set_xticklabels(table.columns)
    ax.set_yticks(range(table.shape[0]))
    ax.set_yticklabels(table.index)
    ax.set_xlabel("Severity")
    ax.set_ylabel("Comment")

    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            prop = proportions.values[i, j]
            if prop > 0:
                ax.text(j, i, f"{prop:.0%}", ha="center", va="center", fontsize=7)

    ax.set_title(
        f"Severity by comment — Cramer's V = {res['cramers_v']:.2f}, "
        f"p = {res['p_value']:.1e} ({res['verdict']})"
    )
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Share of the comment's incidents")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info(
        "Plot saved: %s (Cramer's V=%.3f, p=%.2e)", out.name, res["cramers_v"], res["p_value"]
    )
    return out


def plot_all(df, output_dir: Path) -> list[Path]:
    """Produce the two correlation graphs and return their paths."""
    return [
        plot_severity_signals_correlation(df, output_dir),
        plot_severity_comment_correlation(df, output_dir),
    ]
