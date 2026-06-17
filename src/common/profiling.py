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

logger = logging.getLogger(__name__)

_MAX_UNIQUE_TO_LIST = 20


def _iqr_outlier_count(series: pd.Series) -> int:
    """Number of values outside the 1.5×IQR fences."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return int(((series < low) | (series > high)).sum())


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
    if pd.api.types.is_bool_dtype(s):
        non_na = s.dropna()
        if not non_na.empty:
            entry["pct_true"] = round(100 * float(non_na.mean()), 2)
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


def feature_synthesis_markdown(df: pd.DataFrame, feature: str) -> str:
    """Compact, type-aware markdown synthesis of a single feature (reports + notebook)."""
    e = _profile_column(df[feature], len(df))
    parts = [
        f"- **dtype** {e['dtype']} · **count** {e['count']} · **unique** {e['n_unique']} "
        f"· **missing** {e['n_missing']} ({e['pct_missing']}%)"
    ]
    if "mean" in e:  # numeric
        parts.append(
            f"- **range** {e['min']} → {e['max']} (span {e['range']}) · "
            f"**Q1/median/Q3** {e['q1']} / {e['median']} / {e['q3']}"
        )
        parts.append(
            f"- **mean** {e['mean']} · **std** {e['std']} · **skew** {e['skew']} "
            f"· **IQR outliers** {e['n_outliers_iqr']}"
        )
    elif "ts_min" in e:  # datetime
        parts.append(
            f"- **range** {e['ts_min']:%Y-%m-%d %H:%M} → {e['ts_max']:%Y-%m-%d %H:%M} "
            f"(span {e['span_days']} days)"
        )
    elif "pct_true" in e:  # boolean
        parts.append(f"- **% True** {e['pct_true']}%")
    elif "top_value" in e:  # categorical / text
        parts.append(f"- **most frequent** `{e['top_value']}` ({e['top_count']}, {e['top_pct']}%)")
    if e["n_unique"] <= _MAX_UNIQUE_TO_LIST:
        values = sorted(str(v) for v in df[feature].dropna().unique())
        parts.append(f"- **distinct values**: {', '.join(values)}")
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


def per_feature_markdown(df: pd.DataFrame, graphs_by_feature: dict[str, list[str]]) -> str:
    """Per-feature markdown: for each column, its synthesis then its graphs."""
    lines = ["## Per-feature analysis", ""]
    for col in df.columns:
        lines += [f"### {col}", "", feature_synthesis_markdown(df, col), ""]
        for img in graphs_by_feature.get(col, []):
            lines += [f"![{col}]({img})", ""]
    return "\n".join(lines)


def per_feature_understanding(
    df: pd.DataFrame, numeric_features: list[str], output_dir: Path, machine_col: str
) -> tuple[list[Path], str]:
    """Generate per-feature graphs and the per-feature markdown body.

    For each numeric feature: a boxplot-by-machine (if ``machine_col`` is present)
    and a distribution (histogram + KDE). Every column gets a synthesis.

    Returns
    -------
    tuple[list[pathlib.Path], str]
        The produced graph paths and the per-feature markdown body.
    """
    graphs: list[Path] = []
    graphs_by_feature: dict[str, list[str]] = {}
    features = [f for f in numeric_features if f in df.columns]
    has_machine = machine_col in df.columns
    for i, feature in enumerate(features, start=1):
        images: list[str] = []
        if has_machine:
            box = plot_feature_by_machine(df, feature, i, output_dir, machine_col)
            graphs.append(box)
            images.append(box.name)
        dist = plot_feature_distribution(df, feature, i, output_dir)
        graphs.append(dist)
        images.append(dist.name)
        graphs_by_feature[feature] = images
    return graphs, per_feature_markdown(df, graphs_by_feature)
