"""Generic, source-agnostic feature profiling: descriptive stats + per-feature graphs.

Shared by every source so reports and notebooks use an identical **per-feature**
layout (the telemetry model): for each column a synthesis, and for each numeric
feature a boxplot-by-machine plus a distribution (histogram + density/KDE).
Helps decide imputation / outlier strategies from the data itself.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

from src import config
from src.common import quality

logger = logging.getLogger(__name__)

_MAX_UNIQUE_TO_LIST = 20
_MAX_VERTICAL_BARS = 20  # above this many categories, count bars are drawn horizontally


def _iqr_outlier_count(series: pd.Series) -> int:
    """Number of values outside the 1.5×IQR fences."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return int(((series < low) | (series > high)).sum())


def _is_boolean_like(s: pd.Series) -> bool:
    """True for a boolean column, or a numeric one whose values are all 0/1."""
    if pd.api.types.is_bool_dtype(s):
        return True
    if pd.api.types.is_numeric_dtype(s):
        values = {int(v) for v in s.dropna().unique()}
        return bool(values) and values.issubset({0, 1})
    return False


def _profile_column(s: pd.Series, n: int) -> dict:
    """Descriptive profile of a single column, adapted to its type."""
    n_missing = int(s.isna().sum())
    count = int(s.notna().sum())
    entry = {
        "dtype": str(s.dtype),
        "count": count,
        "n_unique": int(s.nunique(dropna=True)),
        "n_missing": n_missing,
        "pct_missing": round(100 * n_missing / n, 2) if n else 0.0,
    }
    if _is_boolean_like(s):
        entry["is_boolean"] = True  # no numeric stats; 0/1 shares shown in distinct values
    elif pd.api.types.is_numeric_dtype(s):
        num = s.dropna()
        if not num.empty:
            q1, q3 = float(num.quantile(0.25)), float(num.quantile(0.75))
            entry.update(
                {
                    "mean": round(float(num.mean()), 3),
                    "std": round(float(num.std()), 3),
                    "min": round(float(num.min()), 3),
                    "q1": round(q1, 3),
                    "median": round(float(num.median()), 3),
                    "q3": round(q3, 3),
                    "max": round(float(num.max()), 3),
                    "range": round(float(num.max() - num.min()), 3),
                    "skew": round(float(num.skew()), 3),
                    "n_outliers_iqr": _iqr_outlier_count(num),
                }
            )
    elif pd.api.types.is_datetime64_any_dtype(s):
        ts = s.dropna()
        if not ts.empty:
            entry["ts_min"] = ts.min()
            entry["ts_max"] = ts.max()
            entry["span_days"] = int((ts.max() - ts.min()).days)
    else:  # categorical / text
        vc = s.dropna().value_counts()
        if not vc.empty:
            entry["top_value"] = str(vc.index[0])
            entry["top_count"] = int(vc.iloc[0])
            entry["top_pct"] = round(100 * int(vc.iloc[0]) / count, 2) if count else 0.0
    return entry


def profile_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a per-column descriptive profile (one row per feature)."""
    n = len(df)
    rows = [{"feature": col, **_profile_column(df[col], n)} for col in df.columns]
    return pd.DataFrame(rows).set_index("feature")


_STATUS_COLOR = {"OK": "green", "NOK": "red"}


def feature_status_badge(df: pd.DataFrame, feature: str, source: str | None = None) -> str:
    """Colored ``(OK)`` / ``(NOK)`` suffix for a feature heading (``""`` if no criteria).

    Rendered as an inline HTML span (green/red) so it shows up both in the notebook
    and in the markdown reports previewed in VS Code.
    """
    label_status = quality.feature_status(
        feature, _profile_column(df[feature], len(df)), df[feature], df, source
    )
    if label_status is None:
        return ""
    label, _ = label_status
    return f' (<span style="color:{_STATUS_COLOR[label]}">{label}</span>)'


# Purple badge flagging a feature created during Bronze -> Silver processing (shared by the
# processing summary and the Silver per-feature review so both use the exact same marker).
NEW_FEATURE_BADGE = ' <span style="color:purple">(NEW)</span>'


def new_feature_badge(is_new: bool) -> str:
    """Return the ``(NEW)`` badge when ``is_new`` else an empty string."""
    return NEW_FEATURE_BADGE if is_new else ""


def outlier_summary_markdown(series: pd.Series) -> str:
    """Markdown table of flagged outliers by two methods: IQR (k=1.5) and z-score (k=3).

    For each method: the normal band ``[low, high]`` and, on each side, the count and the
    value range of the flagged outliers (``—`` if none). Returns ``""`` for empty input.
    """
    num = pd.to_numeric(series, errors="coerce").dropna()
    if num.empty:
        return ""
    q1, q3 = num.quantile(0.25), num.quantile(0.75)
    iqr = q3 - q1
    mean, std = num.mean(), num.std()
    methods = [("IQR (k=1.5)", float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr))]
    if std and std > 0:
        methods.append(("z-score (k=3)", float(mean - 3 * std), float(mean + 3 * std)))

    def _range(s: pd.Series) -> str:
        return f"[{round(float(s.min()), 3)}, {round(float(s.max()), 3)}]" if len(s) else "—"

    lines = [
        "",
        "**Outliers** — flagged values per method:",
        "",
        "| method | normal band | below — n (range) | above — n (range) |",
        "|---|---|---|---|",
    ]
    for label, low, high in methods:
        below, above = num[num < low], num[num > high]
        lines.append(
            f"| {label} | [{round(low, 3)}, {round(high, 3)}] "
            f"| {len(below)} {_range(below)} | {len(above)} {_range(above)} |"
        )
    return "\n".join(lines)


def outlier_by_machine_markdown(df: pd.DataFrame, feature: str, machine_col: str) -> str:
    """Per-machine outlier counts, with the fences recomputed **within each machine**.

    Complements the global :func:`outlier_summary_markdown`: a value can be normal overall
    yet atypical for its own machine (each machine has its own operating regime). For each
    machine, the IQR (k=1.5) and z-score (k=3) bands are computed on that machine's values
    only, and the below/above counts are reported. Returns ``""`` when there is no machine
    column or fewer than two machines.
    """
    if machine_col not in df.columns or machine_col == feature:
        return ""
    sub = df[[machine_col, feature]].copy()
    sub[feature] = pd.to_numeric(sub[feature], errors="coerce")
    sub = sub.dropna(subset=[feature])
    if sub.empty or sub[machine_col].nunique() < 2:
        return ""

    rows, tot = [], [0, 0, 0, 0]  # iqr_below, iqr_above, z_below, z_above
    for machine, grp in sub.groupby(machine_col):
        v = grp[feature]
        q1, q3 = v.quantile(0.25), v.quantile(0.75)
        iqr = q3 - q1
        iqr_low, iqr_high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        ib, ia = int((v < iqr_low).sum()), int((v > iqr_high).sum())
        mean, std = v.mean(), v.std()
        if std and std > 0:
            zb, za = int((v < mean - 3 * std).sum()), int((v > mean + 3 * std).sum())
        else:
            zb = za = 0
        for i, c in enumerate((ib, ia, zb, za)):
            tot[i] += c
        rows.append((str(machine), len(v), ib, ia, zb, za))
    rows.sort(key=lambda r: r[0])

    lines = [
        "",
        "**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):",
        "",
        "| machine | n | IQR below | IQR above | z-score below | z-score above |",
        "|---|---|---|---|---|---|",
    ]
    lines += [f"| {m} | {n} | {ib} | {ia} | {zb} | {za} |" for m, n, ib, ia, zb, za in rows]
    lines.append(
        f"| **total** | {sum(r[1] for r in rows)} | {tot[0]} | {tot[1]} | {tot[2]} | {tot[3]} |"
    )
    return "\n".join(lines)


def timestamp_qc_markdown(df: pd.DataFrame, time_col: str, machine_col: str) -> str:
    """Per-machine QC table for an hourly timestamp: duplicate stamps + missing hours.

    For each machine: row count, number of duplicate timestamps, and number of missing
    hourly slots between its first and last stamp. Adds a total row.
    """
    ts = pd.to_datetime(df[time_col], errors="coerce")
    grouped = pd.DataFrame({"machine": df[machine_col].to_numpy(), "t": ts}).dropna()
    rows, tot_dup, tot_miss = [], 0, 0
    for machine, grp in grouped.groupby("machine"):
        uniq = grp["t"].drop_duplicates()
        dup = int(grp["t"].duplicated().sum())
        miss = (
            int(len(pd.date_range(uniq.min(), uniq.max(), freq="h")) - len(uniq))
            if len(uniq) >= 2
            else 0
        )
        tot_dup += dup
        tot_miss += miss
        rows.append((str(machine), len(grp), dup, miss))

    lines = [
        "",
        "**Per-machine timestamp QC** (hourly series):",
        "",
        "| machine | rows | duplicate timestamps | missing hours |",
        "|---|---|---|---|",
    ]
    lines += [f"| {m} | {n} | {dup} | {miss} |" for m, n, dup, miss in rows]
    lines.append(f"| **total** | {sum(r[1] for r in rows)} | {tot_dup} | {tot_miss} |")
    return "\n".join(lines)


def shift_time_ranges_markdown(df: pd.DataFrame, shift_col: str, time_col: str) -> str:
    """Per-shift observed time-of-day window, derived from the ``time`` column.

    For each shift value, reports the active ``HH:MM → HH:MM`` window. Overnight shifts
    (whose times wrap past midnight) are detected via the largest cyclic gap in the
    minutes-of-day and flagged ``(overnight)``. Returns ``""`` when no usable time exists.
    """
    pairs = df[[shift_col, time_col]].dropna()
    pairs = pairs[pairs[time_col].astype(str).str.fullmatch(quality.TIME_PATTERN)]
    if pairs.empty:
        return ""

    def _to_min(value: str) -> int:
        text = str(value)
        return int(text[:2]) * 60 + int(text[3:5])

    def _fmt(minute: int) -> str:
        return f"{minute // 60:02d}:{minute % 60:02d}"

    def _window(times: pd.Series) -> tuple[int, str]:
        mins = sorted({_to_min(t) for t in times})
        if len(mins) == 1:
            return mins[0], _fmt(mins[0])
        n = len(mins)
        gaps = [(mins[(i + 1) % n] - mins[i]) % 1440 for i in range(n)]
        gi = max(range(n), key=lambda i: gaps[i])  # largest (inactive) gap
        start, end = mins[(gi + 1) % n], mins[gi]  # active window spans across that gap
        text = f"{_fmt(start)} → {_fmt(end)}"
        return start, (text + " (overnight)" if start > end else text)

    rows = [(str(sh), *_window(grp[time_col])) for sh, grp in pairs.groupby(shift_col)]
    rows.sort(key=lambda r: r[1])  # chronological by window start
    lines = [
        "",
        f"- **time ranges by shift** (derived from `{time_col}`):",
        "",
        "| shift | time range |",
        "|---|---|",
    ]
    lines += [f"| {sh} | {text} |" for sh, _, text in rows]
    return "\n".join(lines)


def feature_synthesis_markdown(df: pd.DataFrame, feature: str, source: str | None = None) -> str:
    """Compact, type-aware markdown synthesis of a single feature (reports + notebook).

    When the feature has declared quality criteria and fails them, a final line lists
    the reason(s); the OK/NOK badge itself goes next to the heading
    (see :func:`feature_status_badge`).
    """
    e = _profile_column(df[feature], len(df))
    parts = [
        f"- **dtype** {e['dtype']} · **count** {e['count']} · **unique** {e['n_unique']} "
        f"· **missing** {e['n_missing']} ({e['pct_missing']}%)"
    ]
    if feature in quality.ID_FEATURES:  # identifier: no extra synthesis line
        pass
    elif "mean" in e and feature in quality.ORDINAL_FEATURES:  # ordinal/discrete: light synthesis
        parts.append(f"- **range** {e['min']} → {e['max']} (span {e['range']})")
    elif "mean" in e:  # numeric (continuous)
        parts.append(
            f"- **range** {e['min']} → {e['max']} (span {e['range']}) · "
            f"**Q1/median/Q3** {e['q1']} / {e['median']} / {e['q3']}"
        )
        parts.append(f"- **mean** {e['mean']} · **std** {e['std']} · **skew** {e['skew']}")
        if feature not in quality.NO_OUTLIER_FEATURES:
            outliers = outlier_summary_markdown(df[feature])
            if outliers:
                parts.append(outliers)
            by_machine = outlier_by_machine_markdown(df, feature, config.MACHINE_COLUMN)
            if by_machine:
                parts.append(by_machine)
    elif "ts_min" in e:  # datetime
        parts.append(
            f"- **range** {e['ts_min']:%Y-%m-%d %H:%M} → {e['ts_max']:%Y-%m-%d %H:%M} "
            f"(span {e['span_days']} days)"
        )
        if feature in quality.HOURLY_PER_MACHINE_FEATURES and config.MACHINE_COLUMN in df.columns:
            parts.append(timestamp_qc_markdown(df, feature, config.MACHINE_COLUMN))
    elif "top_value" in e:  # categorical / text
        non_na = df[feature].dropna().astype(str)
        if not non_na.empty and non_na.str.fullmatch(quality.TIME_PATTERN).all():
            # Time-of-day column: a range is more meaningful than "most frequent".
            parts.append(f"- **range** {non_na.min()} → {non_na.max()}")
        elif feature not in quality.SHARE_FEATURES and e["n_unique"] != e["count"]:
            # Skip "most frequent" for identifier-like columns (every value is unique)
            # and for share features (shown as per-value % below).
            parts.append(
                f"- **most frequent** `{e['top_value']}` ({e['top_count']}, {e['top_pct']}%)"
            )
    if feature not in quality.ID_FEATURES and e["n_unique"] <= _MAX_UNIQUE_TO_LIST:
        non_na = df[feature].dropna()
        if e.get("is_boolean") or feature in quality.SHARE_FEATURES:  # show each value's share
            shares = (non_na.value_counts(normalize=True).sort_index() * 100).round(1)
            values = [f"{v} ({pct}%)" for v, pct in shares.items()]
        else:
            values = sorted(str(v) for v in non_na.unique())
        parts.append(f"- **distinct values**: {', '.join(values)}")
    if feature == config.SHIFT_COLUMN and config.TIME_COLUMN in df.columns:
        ranges = shift_time_ranges_markdown(df, feature, config.TIME_COLUMN)
        if ranges:
            parts.append(ranges)
    label_status = quality.feature_status(feature, e, df[feature], df, source)
    if label_status is not None and label_status[0] == "NOK":
        parts.append(f"- **NOK reason**: {', '.join(label_status[1])}")
    return "\n".join(parts)


def plot_feature_by_machine(
    df: pd.DataFrame, feature: str, index: int, output_dir: Path, machine_col: str
) -> Path:
    """Boxplot of a numeric feature across machines (file ``1.<index>_box_<feature>.png``)."""
    out = Path(output_dir) / f"1.{index}_box_{feature}.png"
    machines = sorted(df[machine_col].dropna().unique())
    data = [
        pd.to_numeric(df.loc[df[machine_col] == m, feature], errors="coerce").dropna().values
        for m in machines
    ]

    fig, ax = plt.subplots(figsize=(max(8, 0.6 * len(machines) + 2), 6))
    ax.boxplot(data, tick_labels=[str(m) for m in machines], showfliers=False)
    ax.set_title(f"{feature} by machine")
    ax.set_xlabel("Machine")
    ax.set_ylabel(feature)
    ax.tick_params(axis="x", rotation=90)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_feature_distribution(df: pd.DataFrame, feature: str, index: int, output_dir: Path) -> Path:
    """Histogram + density curve (KDE) of a feature (file ``2.<index>_dist_<feature>.png``)."""
    data = pd.to_numeric(df[feature], errors="coerce").dropna()
    out = Path(output_dir) / f"2.{index}_dist_{feature}.png"

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(data, bins=50, density=True, color="#4C72B0", alpha=0.6, edgecolor="white")
    if data.nunique() > 1:
        kde = gaussian_kde(data)
        xs = np.linspace(data.min(), data.max(), 200)
        ax.plot(xs, kde(xs), color="#C44E52", linewidth=2, label="density (KDE)")
        ax.legend()
    ax.set_title(f"Distribution of {feature}")
    ax.set_xlabel(feature)
    ax.set_ylabel("Density")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_category_counts(
    df: pd.DataFrame, feature: str, index: int, output_dir: Path, count_label: str = "records"
) -> Path:
    """Bar chart of the record count per category (``3.<index>_count_<feature>.png``).

    Numeric (ordinal) categories are ordered by value (ascending); other categories
    are ordered by descending count. With many categories the bars are drawn
    horizontally (most frequent on top) so the labels stay readable.
    """
    counts = df[feature].value_counts(dropna=True)  # value_counts is already descending
    is_numeric = pd.api.types.is_numeric_dtype(df[feature]) and not pd.api.types.is_bool_dtype(
        df[feature]
    )
    if is_numeric:
        counts = counts.sort_index()  # ordinal: order by category value
    out = Path(output_dir) / f"3.{index}_count_{feature}.png"

    labels = [str(i) for i in counts.index]
    if not is_numeric and len(counts) > _MAX_VERTICAL_BARS:  # many categories → horizontal
        counts = counts[::-1]  # barh draws bottom-up: reverse so the largest is on top
        labels = labels[::-1]
        fig, ax = plt.subplots(figsize=(10, max(6, 0.3 * len(counts) + 2)))
        ax.barh(labels, counts.to_numpy(), color="#4C72B0", edgecolor="white")
        ax.set_xlabel(f"Number of {count_label}")
        ax.set_ylabel(feature)
        ax.grid(True, axis="x", alpha=0.3)
    else:
        fig, ax = plt.subplots(figsize=(max(8, 0.5 * len(counts) + 2), 6))
        ax.bar(labels, counts.to_numpy(), color="#4C72B0", edgecolor="white")
        ax.set_xlabel(feature)
        ax.set_ylabel(f"Number of {count_label}")
        ax.tick_params(axis="x", rotation=90)
        ax.grid(True, axis="y", alpha=0.3)
    ax.set_title(f"{count_label.capitalize()} by {feature}")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


_KEYWORD_STRIP_CHARS = " +/-—"  # separators left around a keyword once it is removed


def _strip_keywords(text: str, keywords: list[str]) -> str:
    """Remove every keyword and surrounding separators from ``text`` (residual comment)."""
    out = text
    for kw in keywords:
        out = out.replace(kw, "")
    return out.strip(_KEYWORD_STRIP_CHARS) or "(none)"


def plot_keyword_breakdown(
    df: pd.DataFrame,
    feature: str,
    keywords: list[str],
    index: int,
    output_dir: Path,
    title: str | None = None,
    count_label: str = "records",
) -> Path:
    """Detail of records whose ``feature`` text contains a keyword.

    Keeps only the matching sub-population (e.g. comments flagging a production stop),
    strips the keyword to recover the residual comment, and draws a horizontal bar per
    residual comment **stacked by the matched keyword** (most frequent on top). File
    ``4.<index>_kw_<feature>.png``.
    """
    text = df[feature].fillna("").astype(str)
    rows = [
        (_strip_keywords(v, keywords), next(kw for kw in keywords if kw in v))
        for v in text
        if any(kw in v for kw in keywords)
    ]
    out = Path(output_dir) / f"4.{index}_kw_{feature}.png"

    ct = pd.crosstab(
        pd.Series([r[0] for r in rows], name="comment"),
        pd.Series([r[1] for r in rows], name="marker"),
    )
    ct = ct.loc[ct.sum(axis=1).sort_values(ascending=False).index][::-1]  # largest on top
    present_kw = [kw for kw in keywords if kw in ct.columns]

    fig, ax = plt.subplots(figsize=(10, max(4, 0.5 * len(ct) + 2)))
    labels = [str(i) for i in ct.index]
    left = np.zeros(len(ct))
    for kw in present_kw:
        vals = ct[kw].to_numpy()
        ax.barh(labels, vals, left=left, label=kw, edgecolor="white")
        left += vals
    for y, total in enumerate(left):
        ax.text(total, y, f" {int(total)}", va="center", fontsize=8)
    ax.set_title(title or f"{feature}: keyword breakdown")
    ax.set_xlabel(f"Number of {count_label}")
    ax.set_ylabel(f"{feature} (marker removed)")
    ax.legend(title="stop type")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_crosstab_heatmap(
    df: pd.DataFrame, row_feature: str, col_feature: str, index: int, output_dir: Path
) -> Path:
    """Row-normalised heatmap of ``row_feature`` × ``col_feature``.

    Each row sums to 100%: it shows how a given ``row_feature`` value spreads across
    ``col_feature`` (e.g. whether a comment maps to a consistent severity). Rows are
    ordered by total frequency (most frequent on top). File
    ``5.<index>_heat_<row>_<col>.png``.
    """
    ct = pd.crosstab(df[row_feature], df[col_feature])
    ct = ct.loc[ct.sum(axis=1).sort_values(ascending=False).index]
    share = ct.div(ct.sum(axis=1), axis=0)
    out = Path(output_dir) / f"5.{index}_heat_{row_feature}_{col_feature}.png"

    fig, ax = plt.subplots(
        figsize=(max(6, 1.4 * len(share.columns) + 3), max(6, 0.35 * len(share) + 2))
    )
    im = ax.imshow(share.to_numpy(), aspect="auto", cmap="YlOrRd", vmin=0, vmax=1)
    ax.set_xticks(range(len(share.columns)), [str(c) for c in share.columns])
    ax.set_yticks(range(len(share.index)), [str(i) for i in share.index])
    ax.set_xlabel(col_feature)
    ax.set_ylabel(row_feature)
    ax.set_title(f"{row_feature} × {col_feature} (row-normalised share)")
    for r in range(len(share.index)):
        for c in range(len(share.columns)):
            ax.text(c, r, f"{share.iat[r, c]:.0%}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_timeseries_by_machine(
    df: pd.DataFrame,
    value_col: str,
    time_col: str,
    machine_col: str,
    index: int,
    output_dir: Path,
    freq: str = "D",
    agg: str = "mean",
    title: str | None = None,
) -> Path:
    """One line per machine: ``value_col`` aggregated over time (``6.<index>_ts_<value_col>.png``).

    For each machine, ``value_col`` is resampled at ``freq`` (default daily) with ``agg``
    (default mean) against ``time_col`` — e.g. the average daily piece production per machine.
    """
    out = Path(output_dir) / f"6.{index}_ts_{value_col}.png"
    data = df[[time_col, machine_col, value_col]].copy()
    data[time_col] = pd.to_datetime(data[time_col], errors="coerce")
    data = data.dropna(subset=[time_col])

    fig, ax = plt.subplots(figsize=(12, 6))
    for machine in sorted(data[machine_col].dropna().unique()):
        series = (
            data[data[machine_col] == machine]
            .set_index(time_col)[value_col]
            .resample(freq)
            .agg(agg)
        )
        ax.plot(series.index, series.to_numpy(), linewidth=1, label=str(machine))
    ax.set_title(title or f"{value_col}: {agg} per '{freq}' by {machine_col}")
    ax.set_xlabel(time_col)
    ax.set_ylabel(f"{agg} {value_col}")
    ax.grid(True, alpha=0.3)
    ax.legend(title=machine_col, fontsize=7, ncol=2, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_cumulative_by_machine(
    df: pd.DataFrame,
    value_col: str,
    time_col: str,
    machine_col: str,
    index: int,
    output_dir: Path,
    title: str | None = None,
) -> Path:
    """One line per machine: running cumulative sum of ``value_col`` over ``time_col``.

    Events are sorted by time and ``value_col`` is accumulated per machine (e.g. the
    cumulative maintenance hours). File ``8.<index>_cum_<value_col>.png``.
    """
    out = Path(output_dir) / f"8.{index}_cum_{value_col}.png"
    data = df[[time_col, machine_col, value_col]].copy()
    data[time_col] = pd.to_datetime(data[time_col], errors="coerce")
    data = data.dropna(subset=[time_col]).sort_values(time_col)

    fig, ax = plt.subplots(figsize=(12, 6))
    for machine in sorted(data[machine_col].dropna().unique()):
        sub = data[data[machine_col] == machine]
        cum = pd.to_numeric(sub[value_col], errors="coerce").fillna(0).cumsum()
        ax.plot(
            sub[time_col], cum.to_numpy(), linewidth=1, drawstyle="steps-post", label=str(machine)
        )
    ax.set_title(title or f"cumulative {value_col} by {machine_col}")
    ax.set_xlabel(time_col)
    ax.set_ylabel(f"cumulative {value_col}")
    ax.grid(True, alpha=0.3)
    ax.legend(title=machine_col, fontsize=7, ncol=2, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def plot_value_by_machine(
    df: pd.DataFrame,
    value_col: str,
    index: int,
    output_dir: Path,
    machine_col: str = config.MACHINE_COLUMN,
) -> Path:
    """Bar chart of ``value_col`` per machine, descending (``7.<index>_barm_<value>.png``).

    Suited to a dimension (one row per machine): each machine's value as a bar, sorted
    from highest to lowest (the per-machine value is taken as the max, identical to the
    single row when there is one row per machine).
    """
    series = df.groupby(machine_col)[value_col].max().sort_values(ascending=False)
    out = Path(output_dir) / f"7.{index}_barm_{value_col}.png"

    fig, ax = plt.subplots(figsize=(max(8, 0.5 * len(series) + 2), 6))
    ax.bar([str(i) for i in series.index], series.to_numpy(), color="#4C72B0", edgecolor="white")
    ax.set_title(f"{value_col} by machine (descending)")
    ax.set_xlabel(machine_col)
    ax.set_ylabel(value_col)
    ax.tick_params(axis="x", rotation=90)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Plot saved: %s", out.name)
    return out


def per_feature_markdown(
    df: pd.DataFrame, graphs_by_feature: dict[str, list[str]], source: str | None = None
) -> str:
    """Per-feature markdown: for each column, its synthesis then its graphs."""
    lines = ["## Per-feature analysis", ""]
    for col in df.columns:
        heading = f"### {col}{feature_status_badge(df, col, source)}"
        lines += [heading, "", feature_synthesis_markdown(df, col, source), ""]
        for img in graphs_by_feature.get(col, []):
            lines += [f"![{col}]({img})", ""]
    return "\n".join(lines)


def per_feature_understanding(
    df: pd.DataFrame,
    numeric_features: list[str],
    output_dir: Path,
    machine_col: str,
    count_features: list[str] = (),
    count_label: str = "records",
    keyword_bars: list[tuple[str, list[str], str]] = (),
    heatmaps: list[tuple[str, str]] = (),
    timeseries: list[tuple[str, str, str, str]] = (),
    bars_by_machine: list[str] = (),
    cumulative: list[tuple[str, str, str]] = (),
    feature_plots: dict | None = None,
    source: str | None = None,
) -> tuple[list[Path], str]:
    """Generate per-feature graphs and the per-feature markdown body.

    For each numeric feature: a boxplot-by-machine (if ``machine_col`` is present)
    and a distribution (histogram + KDE). For each ``count_features`` (categorical):
    a count bar chart. For each ``keyword_bars`` ``(feature, keywords, title)``: a
    keyword-count bar chart. For each ``heatmaps`` ``(row, col)`` pair: a row-normalised
    crosstab heatmap. For each ``timeseries`` ``(value_col, time_col, title, freq)``: a
    per-machine mean line chart at that frequency. Extra graphs are attached to their
    feature. Every column gets a synthesis.

    Returns
    -------
    tuple[list[pathlib.Path], str]
        The produced graph paths and the per-feature markdown body.
    """
    graphs: list[Path] = []
    graphs_by_feature: dict[str, list[str]] = {}
    has_machine = machine_col in df.columns
    for i, feature in enumerate([f for f in numeric_features if f in df.columns], start=1):
        images: list[str] = []
        if has_machine:
            box = plot_feature_by_machine(df, feature, i, output_dir, machine_col)
            graphs.append(box)
            images.append(box.name)
        dist = plot_feature_distribution(df, feature, i, output_dir)
        graphs.append(dist)
        images.append(dist.name)
        graphs_by_feature[feature] = images
    for j, feature in enumerate([f for f in count_features if f in df.columns], start=1):
        bar = plot_category_counts(df, feature, j, output_dir, count_label)
        graphs.append(bar)
        graphs_by_feature.setdefault(feature, []).append(bar.name)
    present_kw = [(f, kw, title) for f, kw, title in keyword_bars if f in df.columns]
    for m, (feature, kw, title) in enumerate(present_kw, start=1):
        bar = plot_keyword_breakdown(df, feature, kw, m, output_dir, title, count_label)
        graphs.append(bar)
        graphs_by_feature.setdefault(feature, []).append(bar.name)
    present_heatmaps = [(r, c) for r, c in heatmaps if r in df.columns and c in df.columns]
    for k, (row_feature, col_feature) in enumerate(present_heatmaps, start=1):
        heat = plot_crosstab_heatmap(df, row_feature, col_feature, k, output_dir)
        graphs.append(heat)
        graphs_by_feature.setdefault(row_feature, []).append(heat.name)
    present_ts = [
        (v, t, title, freq)
        for v, t, title, freq in timeseries
        if v in df.columns and t in df.columns
    ]
    for n, (value_col, time_col, title, freq) in enumerate(present_ts, start=1):
        ts = plot_timeseries_by_machine(
            df, value_col, time_col, machine_col, n, output_dir, freq=freq, title=title
        )
        graphs.append(ts)
        graphs_by_feature.setdefault(value_col, []).append(ts.name)
    for q, value_col in enumerate([f for f in bars_by_machine if f in df.columns], start=1):
        bar = plot_value_by_machine(df, value_col, q, output_dir)
        graphs.append(bar)
        graphs_by_feature.setdefault(value_col, []).append(bar.name)
    present_cum = [
        (v, t, title) for v, t, title in cumulative if v in df.columns and t in df.columns
    ]
    for r, (value_col, time_col, title) in enumerate(present_cum, start=1):
        cum = plot_cumulative_by_machine(df, value_col, time_col, machine_col, r, output_dir, title)
        graphs.append(cum)
        graphs_by_feature.setdefault(value_col, []).append(cum.name)
    for feature, plot_fn in (feature_plots or {}).items():
        if feature in df.columns:
            for path in plot_fn(df, output_dir):
                graphs.append(path)
                graphs_by_feature.setdefault(feature, []).append(path.name)
    return graphs, per_feature_markdown(df, graphs_by_feature, source)
