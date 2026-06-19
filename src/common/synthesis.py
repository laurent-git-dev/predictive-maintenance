"""Cross-source synthesis table: per-feature status + suggested Bronze -> Silver processing."""

from __future__ import annotations

import pandas as pd

from src import config
from src.common import coherence, profiling, quality

_STATUS_COLOR = {"OK": "green", "NOK": "red"}


def _status_cell(status: str) -> str:
    if status in _STATUS_COLOR:
        return f'<span style="color:{_STATUS_COLOR[status]}">{status}</span>'
    return "—"  # no criteria declared


def _format_hint(feature: str, profile: dict, series: pd.Series) -> str | None:
    """Format-harmonisation reminder for date / time / timestamp features."""
    if "ts_min" in profile:  # datetime column
        return "harmonise format / timezone (consistent datetime)"
    non_na = series.dropna().astype(str)
    if (
        "top_value" in profile
        and not non_na.empty
        and non_na.str.fullmatch(quality.TIME_PATTERN).all()
    ):
        return "harmonise time format (HH:MM[:SS])"
    return None


def _encode_hint(feature: str, profile: dict, series: pd.Series) -> str | None:
    """Encoding suggestion for a text/categorical feature (none for ids / time / all-unique)."""
    if "top_value" not in profile:  # not a text column (numeric/datetime/boolean)
        return None
    if feature in quality.ID_FEATURES or profile["n_unique"] == profile["count"]:
        return None  # identifier-like: do not encode
    non_na = series.dropna().astype(str)
    if not non_na.empty and non_na.str.fullmatch(quality.TIME_PATTERN).all():
        return None  # time-of-day, handled as time
    return "text -> value: encode (label/ordinal/one-hot)"


def _outlier_hint(feature: str, profile: dict) -> str | None:
    """Outlier hypothesis for a continuous numeric feature (none for id/ordinal/boolean)."""
    if feature in quality.ID_FEATURES or feature in quality.ORDINAL_FEATURES:
        return None
    if feature in quality.NO_OUTLIER_FEATURES:
        return None
    n = profile.get("n_outliers_iqr")
    if not n:
        return None
    return f"outliers (IQR n={n}): hypotheses -> winsorise/clip, cap, transform, or keep if valid"


def bronze_synthesis_markdown(dfs_by_source: dict[str, pd.DataFrame]) -> str:
    """Recap table of every feature per source: status + suggested processing to Silver."""
    lines = [
        "| Source | Feature | Status | Suggested processing (Bronze -> Silver) |",
        "|---|---|---|---|",
    ]
    for source, df in dfs_by_source.items():
        n = len(df)
        for col in df.columns:
            profile = profiling._profile_column(df[col], n)
            status, failing = quality.feature_report(col, profile, df[col], df, source)
            suggestions = [sugg for _, sugg in failing if sugg]
            for hint in (
                _format_hint(col, profile, df[col]),
                _encode_hint(col, profile, df[col]),
                _outlier_hint(col, profile),
            ):
                if hint:
                    suggestions.append(hint)
            cell = " ; ".join(suggestions) if suggestions else "—"
            label = config.SOURCE_DISPLAY_NAMES.get(source, source)
            lines.append(f"| {label} | {col} | {_status_cell(status)} | {cell} |")
    # Cross-source checks (section 1.6.1) appended as a final block.
    for name, ok in coherence.cross_check_statuses(dfs_by_source):
        status = "OK" if ok else "NOK"
        note = "—" if ok else "review inconsistency (see 1.6.1)"
        lines.append(f"| cross-check | {name} | {_status_cell(status)} | {note} |")
    return "\n".join(lines)
