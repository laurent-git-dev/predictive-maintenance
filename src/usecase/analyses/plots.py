"""Cross-source plots, computed from the joined tables."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt

from src import config

logger = logging.getLogger(__name__)

_CRITICALITY_COLORS = {"LOW": "#55A868", "MEDIUM": "#DD8452", "HIGH": "#C44E52"}


def _criticality_colors(profile) -> list[str]:
    return [
        _CRITICALITY_COLORS.get(c, "#4C72B0") for c in profile[config.MACHINE_CRITICALITY_COLUMN]
    ]


def _legend_handles():
    from matplotlib.patches import Patch

    return [Patch(color=c, label=k) for k, c in _CRITICALITY_COLORS.items()]


def plot_incidents_vs_maintenance(profile, output_dir: Path) -> Path:
    """Scatter of incidents vs maintenance per machine, coloured by criticality."""
    out = Path(output_dir) / "1_incidents_vs_maintenance.png"

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(
        profile["n_maintenance"], profile["n_incidents"], c=_criticality_colors(profile), s=80
    )
    for _, row in profile.iterrows():
        ax.annotate(
            str(row[config.MACHINE_COLUMN]),
            (row["n_maintenance"], row["n_incidents"]),
            fontsize=7,
            xytext=(3, 3),
            textcoords="offset points",
        )
    ax.set_xlabel("Number of maintenance events")
    ax.set_ylabel("Number of incidents")
    ax.set_title("Incidents vs maintenance per machine")
    ax.legend(handles=_legend_handles(), title="criticality")
    ax.grid(True, alpha=0.3)
    _save(fig, out)
    return out


def plot_reactive_vs_severity(reactive_join, output_dir: Path) -> Path:
    """Reactive maintenances by triggering incident severity (count + mean duration)."""
    out = Path(output_dir) / "2_reactive_vs_severity.png"

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    if reactive_join.empty:
        for ax in axes:
            ax.text(0.5, 0.5, "No reactive↔incident match", ha="center", va="center")
            ax.set_axis_off()
        _save(fig, out)
        return out

    counts = reactive_join[config.SEVERITY_COLUMN].value_counts().sort_index()
    axes[0].bar(counts.index.astype(str), counts.values, color="#C44E52")
    axes[0].set_title("Reactive maintenances by incident severity")
    axes[0].set_xlabel("Incident severity")
    axes[0].set_ylabel("Number of reactive maintenances")
    axes[0].grid(True, axis="y", alpha=0.3)

    dur = reactive_join.groupby(config.SEVERITY_COLUMN)[config.MAINTENANCE_DURATION_COLUMN].mean()
    axes[1].bar(dur.index.astype(str), dur.values, color="#937860")
    axes[1].set_title("Mean repair duration by incident severity")
    axes[1].set_xlabel("Incident severity")
    axes[1].set_ylabel("Mean duration (hours)")
    axes[1].grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_telemetry_vs_incidents(profile, output_dir: Path) -> Path:
    """Scatter of mean temperature vs incident count per machine."""
    out = Path(output_dir) / "3_telemetry_vs_incidents.png"
    x_col = "mean_temperature_c"

    fig, ax = plt.subplots(figsize=(9, 7))
    if x_col in profile.columns:
        corr = profile[[x_col, "n_incidents"]].corr().iloc[0, 1]
        ax.scatter(profile[x_col], profile["n_incidents"], c=_criticality_colors(profile), s=80)
        for _, row in profile.iterrows():
            ax.annotate(
                str(row[config.MACHINE_COLUMN]),
                (row[x_col], row["n_incidents"]),
                fontsize=7,
                xytext=(3, 3),
                textcoords="offset points",
            )
        ax.set_xlabel("Mean temperature (°C)")
        ax.set_ylabel("Number of incidents")
        ax.set_title(f"Mean temperature vs incidents per machine (corr = {corr:.2f})")
        ax.legend(handles=_legend_handles(), title="criticality")
        ax.grid(True, alpha=0.3)
    _save(fig, out)
    return out


def plot_all(profile, reactive_join, output_dir: Path) -> list[Path]:
    """Produce the three cross-source plots and return their paths."""
    return [
        plot_incidents_vs_maintenance(profile, output_dir),
        plot_reactive_vs_severity(reactive_join, output_dir),
        plot_telemetry_vs_incidents(profile, output_dir),
    ]


def _save(fig, out: Path) -> None:
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
