"""Overview helpers for the two machines.sql sources (dimension + maintenance)."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import config

logger = logging.getLogger(__name__)

# Hierarchy levels of the machine tree (leaves = machine_id).
TREE_LEVELS: tuple[str, ...] = (
    config.MACHINE_LOCATION_COLUMN,
    config.MACHINE_LINE_COLUMN,
    config.MACHINE_CRITICALITY_COLUMN,
    config.MACHINE_MODEL_COLUMN,
)


def machine_tree_markdown(
    df: pd.DataFrame,
    levels: tuple[str, ...] = TREE_LEVELS,
    leaf: str = config.MACHINE_COLUMN,
) -> str:
    """Indented tree of the machines grouped by ``levels`` (leaves = ``leaf``).

    Renders as a fenced code block: location -> production_line -> criticality ->
    model -> machine_id, each grouping node annotated with its machine count.
    """
    lines: list[str] = ["```"]

    def walk(sub: pd.DataFrame, depth: int) -> None:
        if depth == len(levels):
            for value in sorted(sub[leaf].astype(str)):
                lines.append("    " * depth + value)
            return
        col = levels[depth]
        for value, group in sorted(sub.groupby(col), key=lambda kv: str(kv[0])):
            lines.append("    " * depth + f"{value}  ({len(group)})")
            walk(group, depth + 1)

    walk(df, 0)
    lines.append("```")
    return "\n".join(lines)


def plot_maintenance_count_over_time(
    df: pd.DataFrame, output_dir: Path, maintenance_type: str, index: int, freq: str = "ME"
) -> Path:
    """One line per machine: count of ``maintenance_type`` maintenances over time.

    Events are filtered to ``maintenance_type`` and counted per machine per ``freq``
    (default month). File ``overview_<index>_<maintenance_type>_over_time.png``.
    """
    out = Path(output_dir) / f"overview_{index}_{maintenance_type}_over_time.png"
    sub = df[df[config.MAINTENANCE_TYPE_COLUMN] == maintenance_type].copy()
    sub["_t"] = pd.to_datetime(sub[config.MAINTENANCE_TIMESTAMP_COLUMN], errors="coerce")
    sub = sub.dropna(subset=["_t"])
    counts = (
        sub.groupby([pd.Grouper(key="_t", freq=freq), config.MACHINE_COLUMN])
        .size()
        .unstack(config.MACHINE_COLUMN)
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    for machine in sorted(counts.columns):
        ax.plot(counts.index, counts[machine], linewidth=1, label=str(machine))
    ax.set_title(
        f"{maintenance_type.capitalize()} maintenances over time by machine (per '{freq}')"
    )
    ax.set_xlabel(config.MAINTENANCE_TIMESTAMP_COLUMN)
    ax.set_ylabel("number of maintenances")
    ax.grid(True, alpha=0.3)
    ax.legend(
        title=config.MACHINE_COLUMN,
        fontsize=7,
        ncol=2,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
    )
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def maintenance_overview_plots(df: pd.DataFrame, output_dir: Path) -> list[Path]:
    """Whole-source maintenance overview: proactive then reactive counts over time."""
    return [
        plot_maintenance_count_over_time(df, output_dir, "proactive", 1),
        plot_maintenance_count_over_time(df, output_dir, "reactive", 2),
    ]


def plot_capacity_coherence(machine_df: pd.DataFrame, output_dir: Path) -> list[Path]:
    """One panel per machine: theoretical cumulative output from each declared capacity.

    Purely from the machine referential (no telemetry), over a single 24h day:
    - **hourly basis**: ``max_hourly_capacity_pieces`` * hours (output if running 24h at the cap);
    - **daily basis**: ``max_daily_capacity`` spread linearly across 24h.

    The two diverge because ``max_daily_capacity`` ~= ``max_hourly_capacity_pieces`` * 16 (a
    16h shift), so running at the hourly cap for a full 24h day reaches ~1.5x the daily cap. The
    hour where the hourly line meets the daily ceiling (vertical marker) is the implied
    operating-day length.
    """
    mc = config.MACHINE_COLUMN
    daily_cap, hourly_cap = config.MACHINE_MAX_DAILY_COLUMN, config.MACHINE_MAX_HOURLY_COLUMN
    ref = machine_df[[mc, hourly_cap, daily_cap]].dropna().sort_values(mc)
    if ref.empty:
        return []

    hours = list(range(25))
    machines = ref[mc].tolist()
    ncols = 3
    nrows = -(-len(machines) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 3.2 * nrows), sharex=True)
    axes = axes.flatten()
    for ax, (_, row) in zip(axes, ref.iterrows(), strict=False):
        ch, cd = row[hourly_cap], row[daily_cap]
        implied = cd / ch if ch else 0
        ax.plot(
            hours,
            [ch * h for h in hours],
            color="#55A868",
            linewidth=1.4,
            label="max_hourly_capacity_pieces x hours (24h/day)",
        )
        ax.plot(
            hours,
            [cd * h / 24 for h in hours],
            color="#4C72B0",
            linewidth=1.4,
            linestyle="--",
            label="max_daily_capacity spread over 24h",
        )
        ax.axhline(cd, color="#888888", linewidth=0.8, linestyle=":")
        ax.axvline(implied, color="#C44E52", linewidth=0.8, linestyle=":")
        ax.set_title(f"{row[mc]} (daily ~= {implied:.1f}x hourly)", fontsize=9)
        ax.set_xlim(0, 24)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)
    for ax in axes[len(machines) :]:
        ax.set_visible(False)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, fontsize=9)
    fig.suptitle(
        "Capacity coherence per machine: hourly vs daily cap over a 24h day "
        "(dotted red = implied operating hours)",
        y=0.995,
    )
    fig.supxlabel("hour of day")
    fig.supylabel("cumulative pieces (theoretical)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    path = output_dir / "capacity_coherence.png"
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return [path]
