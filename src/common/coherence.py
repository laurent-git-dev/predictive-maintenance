"""Cross-source coherence checks (Bronze): each renders a status badge + explanations.

Mirrors the per-feature status style: every check is shown as ``##### <name> (OK/NOK)``;
when NOK, an explanation block details the inconsistency.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import config

_STATUS_COLOR = {"OK": "green", "NOK": "red"}


def _label(source: str) -> str:
    return config.SOURCE_DISPLAY_NAMES.get(source, source)


@dataclass(frozen=True)
class CrossCheck:
    """A named cross-source check returning ``(ok, explanation_markdown)``."""

    name: str
    run: Callable[[dict[str, pd.DataFrame]], tuple[bool, str]]


def _machine_id_consistency(dfs: dict[str, pd.DataFrame]) -> tuple[bool, str]:
    """Every machine_id used in a source must exist in the ``machine`` referential."""
    col = config.MACHINE_COLUMN
    if "machine" not in dfs or col not in dfs["machine"].columns:
        return True, "_No machine referential available to check against._"
    reference = set(dfs["machine"][col].dropna().unique())

    rows, orphans_by_source = [], {}
    for name, df in dfs.items():
        if col not in df.columns:
            continue
        values = set(df[col].dropna().unique())
        orphans = sorted(values - reference)
        missing = sorted(reference - values)  # machines never seen in this source (informational)
        if orphans:
            orphans_by_source[name] = orphans
        rows.append((_label(name), len(values), len(orphans), len(missing)))

    ok = not orphans_by_source
    lines = [
        f"Referential `machine`: **{len(reference)}** machines. (Status checks every used "
        "machine_id exists in it; with 0 orphans and 0 not-covered, every source uses the "
        "**same** machine_id set.)",
        "",
        "| source | distinct machine_id | orphans (not in referential) | not covered |",
        "|---|---|---|---|",
    ]
    lines += [f"| {n} | {d} | {o} | {miss} |" for n, d, o, miss in rows]
    if orphans_by_source:
        lines.append("")
        for name, orphans in orphans_by_source.items():
            lines.append(f"- **{_label(name)}** references unknown machine_id: {orphans}")
    return ok, "\n".join(lines)


def _related_incident_referential(dfs: dict[str, pd.DataFrame]) -> tuple[bool, str]:
    """Every related_incident_id in maintenance must exist in incidents (FK integrity)."""
    inc_col, rel_col = config.ID_COLUMN, config.MAINTENANCE_INCIDENT_COLUMN
    if "incidents" not in dfs or "machines" not in dfs:
        return True, "_incidents / maintenance not both available._"
    incident_ids = set(dfs["incidents"][inc_col].dropna().unique())
    related = dfs["machines"][rel_col].dropna()
    related_ids = set(related.unique())

    orphans = sorted(related_ids - incident_ids)
    unreferenced = sorted(incident_ids - related_ids)  # incidents with no maintenance (info)
    ok = not orphans
    lines = [
        f"`machines/maintenance.related_incident_id`: **{len(related)}** non-null "
        f"(**{len(related_ids)}** distinct) · `incidents.incident_id`: "
        f"**{len(incident_ids)}** distinct.",
        "",
        f"- orphans (related_incident_id absent from incidents): **{len(orphans)}**",
        f"- _(info)_ incidents not referenced by any maintenance: **{len(unreferenced)}**",
    ]
    if orphans:
        lines.append(f"  - examples: {orphans[:10]}" + (" …" if len(orphans) > 10 else ""))
    if unreferenced:
        lines.append(
            f"  - info examples: {unreferenced[:10]}" + (" …" if len(unreferenced) > 10 else "")
        )
    return ok, "\n".join(lines)


def _pieces_within_capacity(dfs: dict[str, pd.DataFrame]) -> tuple[bool, str]:
    """telemetry `pieces_produced` must respect the machine hourly capacity (per-hour vs per-hour).

    Unit note: telemetry is sampled hourly, so each `pieces_produced` reading is a per-hour
    count and is directly comparable to `max_hourly_capacity_pieces`. `max_daily_capacity`
    is a 16h-shift figure (~= max_hourly * 16) and is NOT comparable to a 24h sum of readings,
    so it is reported for context only and excluded from the pass/fail decision.
    """
    if "telemetry" not in dfs or "machine" not in dfs:
        return True, "_telemetry / machine not both available._"
    mc, pcol, tcol = (
        config.MACHINE_COLUMN,
        config.TELEMETRY_PIECES_COLUMN,
        config.TELEMETRY_TIMESTAMP_COLUMN,
    )
    hourly_cap, daily_cap = config.MACHINE_MAX_HOURLY_COLUMN, config.MACHINE_MAX_DAILY_COLUMN
    caps = dfs["machine"][[mc, hourly_cap, daily_cap]]
    t = dfs["telemetry"][[mc, tcol, pcol]].merge(caps, on=mc, how="left")

    n = len(t)
    over = t[t[pcol] > t[hourly_cap]].copy()
    hourly_over = len(over)
    ratio = round(daily_cap_to_hourly(caps, hourly_cap, daily_cap), 1)
    ok = hourly_over == 0
    lines = [
        f"Telemetry is hourly, so each `pieces_produced` reading is compared to the per-hour "
        f"capacity (`max_hourly_capacity_pieces`). `max_daily_capacity` averages ~{ratio}x the "
        f"hourly cap (a 16h-shift figure), not a 24h total, so it is excluded from the check.",
        "",
        f"- hourly readings with `pieces_produced` > `max_hourly_capacity_pieces`: "
        f"**{hourly_over}** / {n} ({round(100 * hourly_over / n, 1)}%), "
        f"spanning **{over[mc].nunique()}** / {t[mc].nunique()} machines",
    ]
    if not ok:
        over["over_by"] = over[pcol] - over[hourly_cap]
        worst = over.sort_values("over_by", ascending=False).head(5)
        lines.append(
            "  - production exceeds the declared per-hour capacity -> review the referential "
            "capacities or the telemetry counts. Worst overshoots:"
        )
        lines.append("")
        lines.append("| machine_id | timestamp | pieces_produced | max_hourly_capacity_pieces |")
        lines.append("|---|---|---|---|")
        for _, r in worst.iterrows():
            lines.append(f"| {r[mc]} | {r[tcol]} | {int(r[pcol])} | {int(r[hourly_cap])} |")
    return ok, "\n".join(lines)


def daily_cap_to_hourly(caps: pd.DataFrame, hourly_cap: str, daily_cap: str) -> float:
    """Mean ratio max_daily_capacity / max_hourly_capacity_pieces (operating hours implied)."""
    return float((caps[daily_cap] / caps[hourly_cap]).mean())


def plot_pieces_vs_capacity(dfs: dict[str, pd.DataFrame], output_dir: Path) -> list[Path]:
    """One panel per machine: real cumulative production vs both theoretical-capacity maxima.

    Real cumulative = running sum of telemetry ``pieces_produced``. Two theoretical ceilings
    from the machine referential, accrued linearly over elapsed time:
    - **daily capacity**: ``max_daily_capacity`` per elapsed day;
    - **hourly capacity**: ``max_hourly_capacity_pieces`` per elapsed hour (i.e. 24h/day).

    Real production sitting above the daily line but below the hourly line is the over-capacity
    finding: output is impossible under the (16h-shift) daily cap, yet fits the per-hour cap.
    """
    if "telemetry" not in dfs or "machine" not in dfs:
        return []
    mc, pcol, tcol = (
        config.MACHINE_COLUMN,
        config.TELEMETRY_PIECES_COLUMN,
        config.TELEMETRY_TIMESTAMP_COLUMN,
    )
    ref = dfs["machine"].set_index(mc)
    cap_d, cap_h = ref[config.MACHINE_MAX_DAILY_COLUMN], ref[config.MACHINE_MAX_HOURLY_COLUMN]

    t = dfs["telemetry"][[mc, tcol, pcol]].copy()
    t["t"] = pd.to_datetime(t[tcol], errors="coerce")
    t = t.dropna(subset=["t"]).sort_values("t")
    machines = sorted(m for m in t[mc].dropna().unique() if m in cap_d.index)
    if not machines:
        return []

    ncols = 3
    nrows = -(-len(machines) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 3.2 * nrows), sharex=True)
    axes = axes.flatten()
    for ax, mid in zip(axes, machines, strict=False):
        g = t[t[mc] == mid]
        elapsed_days = (g["t"] - g["t"].iloc[0]) / pd.Timedelta(days=1)
        elapsed_hours = (g["t"] - g["t"].iloc[0]) / pd.Timedelta(hours=1)
        ax.plot(
            g["t"],
            cap_h[mid] * elapsed_hours,
            color="#55A868",
            linewidth=1.2,
            linestyle=":",
            label="theoretical max (hourly capacity, 24h/day)",
        )
        ax.plot(g["t"], g[pcol].cumsum(), color="#C44E52", linewidth=1.3, label="real cumulative")
        ax.plot(
            g["t"],
            cap_d[mid] * elapsed_days,
            color="#4C72B0",
            linewidth=1.3,
            linestyle="--",
            label="theoretical max (daily capacity)",
        )
        ax.set_title(str(mid), fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)
    for ax in axes[len(machines) :]:
        ax.set_visible(False)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, fontsize=9)
    fig.suptitle(
        "Cumulative real production vs theoretical maxima (daily & hourly capacity) per machine",
        y=0.995,
    )
    fig.supylabel("cumulative pieces_produced")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    path = output_dir / "pieces_vs_capacity_cumulative.png"
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return [path]


def _temporal_coverage(dfs: dict[str, pd.DataFrame]) -> tuple[bool, str]:
    """The dated sources (incidents, telemetry, maintenance) must cover the same period."""
    sources = [
        ("incidents", config.DATE_COLUMN),
        ("telemetry", config.TELEMETRY_TIMESTAMP_COLUMN),
        ("machines", config.MAINTENANCE_TIMESTAMP_COLUMN),
    ]
    rows = []
    for src, col in sources:
        if src in dfs and col in dfs[src].columns:
            t = pd.to_datetime(dfs[src][col], errors="coerce", utc=True).dropna()
            if not t.empty:
                rows.append((src, t.min().normalize(), t.max().normalize(), len(t)))
    if len(rows) < 2:
        return True, "_fewer than two dated sources available to compare._"

    tol = pd.Timedelta(days=7)
    starts = {r[0]: r[1] for r in rows}
    ends = {r[0]: r[2] for r in rows}
    start_spread = max(starts.values()) - min(starts.values())
    end_spread = max(ends.values()) - min(ends.values())
    overlap_start, overlap_end = max(starts.values()), min(ends.values())
    has_overlap = overlap_start <= overlap_end
    ok = has_overlap and start_spread <= tol and end_spread <= tol

    def _d(ts: pd.Timestamp) -> str:
        return ts.strftime("%Y-%m-%d")

    common = (
        f"**{_d(overlap_start)} → {_d(overlap_end)}**" if has_overlap else "**none (no overlap)**"
    )
    lines = [
        f"Aligned-coverage tolerance: **{tol.days} days**. Common overlap window: {common} "
        f"(start spread {start_spread.days}d, end spread {end_spread.days}d).",
        "",
        "| source | first | last | span (days) | rows |",
        "|---|---|---|---|---|",
    ]
    for src, smin, smax, n in rows:
        lines.append(f"| {_label(src)} | {_d(smin)} | {_d(smax)} | {(smax - smin).days} | {n} |")
    if not ok:
        lines.append("")
        if not has_overlap:
            lines.append("- **no common period**: the sources' date ranges do not overlap.")
        if start_spread > tol:
            early, late = min(starts, key=starts.get), max(starts, key=starts.get)
            lines.append(
                f"- **start misaligned** by {start_spread.days} days: earliest {_label(early)} "
                f"({_d(starts[early])}) vs latest {_label(late)} ({_d(starts[late])})."
            )
        if end_spread > tol:
            early, late = min(ends, key=ends.get), max(ends, key=ends.get)
            lines.append(
                f"- **end misaligned** by {end_spread.days} days: earliest {_label(early)} "
                f"({_d(ends[early])}) vs latest {_label(late)} ({_d(ends[late])})."
            )
    return ok, "\n".join(lines)


CROSS_CHECKS: list[CrossCheck] = [
    CrossCheck("machine_id consistency across sources", _machine_id_consistency),
    CrossCheck("related_incident_id present in incidents", _related_incident_referential),
    CrossCheck("pieces_produced within machine capacity", _pieces_within_capacity),
    CrossCheck("temporal coverage aligned across sources", _temporal_coverage),
]


def cross_check_statuses(dfs_by_source: dict[str, pd.DataFrame]) -> list[tuple[str, bool]]:
    """``(check name, ok)`` for every cross-source check — used by the synthesis recap."""
    return [(check.name, check.run(dfs_by_source)[0]) for check in CROSS_CHECKS]


def cross_checks_markdown(dfs_by_source: dict[str, pd.DataFrame]) -> str:
    """Render every cross-source check as ``##### <name> (OK/NOK)`` + explanation."""
    blocks = []
    for check in CROSS_CHECKS:
        ok, explanation = check.run(dfs_by_source)
        status = "OK" if ok else "NOK"
        badge = f'<span style="color:{_STATUS_COLOR[status]}">{status}</span>'
        blocks.append(f"##### {check.name} ({badge})\n\n{explanation}")
    return "\n\n".join(blocks)
