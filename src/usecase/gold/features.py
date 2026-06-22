"""Unified Gold feature table — one row per ``(machine_id, 1-hour window)``.

Built from the three (clean) Silver frames into a single training-ready table. The decision
instant of a row is ``t = window_end``: **backward** windows (memory / trend / anomaly /
context) look up to and **including** the current hour; **labels** look **strictly after**
``t``. A *failure* is an incident of **severity >= 4**.

Telemetry is a contiguous hourly grid per machine, so the ``-Nh`` windows are exact
(count-based). Feature groups: identifiers, memory (rolling mean/max/std), trend (rolling
OLS slope), anomaly (z-scores), context (incidents / signals / maintenance) and labels.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src import config
from src.framework.timeutils import to_naive_hour

logger = logging.getLogger(__name__)

MEASURES = list(config.TELEMETRY_PARAM_COLUMNS)  # 5 telemetry measures (incl. pieces_produced)
SIGNALS = list(config.SIGNAL_COLUMNS)  # 9 type_* signals
MEM_H = [2, 3, 4, 6, 12, 24, 48]  # memory horizons (hours)
TREND_H = [2, 3, 4, 5, 6]  # trend horizons (hours)
EVENT_H = [("6h", 6), ("12h", 12), ("24h", 24), ("48h", 48), ("7d", 168)]  # incident/signal (hours)
MNT_D = [("5d", 5), ("10d", 10), ("20d", 20), ("30d", 30), ("60d", 60)]  # maintenance (days)
LABEL_H = [("6h", 6), ("12h", 12), ("24h", 24), ("48h", 48)]  # label horizons (hours)
WS, WE = "window_start", "window_end"

# Representative subset for the layer profiling (the full table is ~216 columns).
FEATURES_NUMERIC = [
    *[f"{m}_mean_24h" for m in MEASURES],
    *[f"{m}_z_machine" for m in MEASURES],
    "inc_hours_since_last",
    "mnt_corr_days_since_last",
]
FEATURES_COUNT = [
    "label_failure_next_6h",
    "label_failure_next_24h",
    "label_failure_next_48h",
    "inc_count_24h",
    "mnt_corr_count_30d",
]


def _floor_hour(series: pd.Series) -> pd.Series:
    """Parse, drop timezone (maintenance_at is UTC) and floor to the hour (shared util)."""
    return to_naive_hour(series)


def _slope(y: np.ndarray) -> float:
    """OLS slope (per hour) of ``y`` against its 0..n-1 position; NaN if < 2 points."""
    n = y.shape[0]
    if n < 2:
        return np.nan
    x = np.arange(n, dtype=float)
    dx = x - x.mean()
    denom = float((dx * dx).sum())
    return float((dx * (y - y.mean())).sum() / denom) if denom else np.nan


def _hours_since_last(df: pd.DataFrame, hour_flag: str, mc: str) -> pd.Series:
    """Hours since the most recent past hour (<= t) where ``hour_flag`` > 0 (NA before first)."""
    event_hour = df[WS].where(df[hour_flag] > 0)
    last = event_hour.groupby(df[mc]).ffill()
    return (df[WS] - last).dt.total_seconds() / 3600


def _future_failure(df: pd.DataFrame, hour_flag: str, mc: str, horizon: int) -> pd.Series:
    """1 if any ``hour_flag`` event in ``(t, t+horizon]`` hours; NA if the window is censored.

    Censored = the future window extends beyond the machine's last observed hour.
    """
    out = pd.Series(np.nan, index=df.index, dtype="float64")
    for _, idx in df.groupby(mc, sort=False).groups.items():
        sub = df.loc[idx].sort_values(WS)
        f = (pd.to_numeric(sub[hour_flag], errors="coerce") > 0).astype(int).to_numpy()
        n = len(f)
        cum = np.concatenate([[0], np.cumsum(f)])
        vals = np.full(n, np.nan)
        for i in range(n):
            if i + horizon <= n - 1:  # full future window observed
                vals[i] = cum[i + horizon + 1] - cum[i + 1]
        out.loc[sub.index] = vals
    label = pd.Series(pd.NA, index=df.index, dtype="Int64")
    mask = out.notna()
    label[mask] = (out[mask] > 0).astype("Int64")
    return label


def _per_hour_tables(silver: dict, mc: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate incident & maintenance events to per-(machine, hour) helper columns."""
    inc = silver["incidents"].copy()
    inc[WS] = _floor_hour(
        inc[config.DATE_COLUMN].astype(str) + " " + inc[config.TIME_COLUMN].astype(str)
    )
    inc = inc.dropna(subset=[WS])
    sev = pd.to_numeric(inc[config.SEVERITY_COLUMN], errors="coerce")
    inc = inc.assign(_sev=sev, _fail=(sev >= 4).astype(int))
    g = inc.groupby([mc, WS], sort=False)
    inc_hour = g.agg(_inc=("_sev", "size"), _sevmax=("_sev", "max"), _fail=("_fail", "max"))
    inc_hour = inc_hour.join(g[SIGNALS].sum()).reset_index()

    mnt = silver["maintenance"].copy()
    mnt[WS] = _floor_hour(mnt[config.MAINTENANCE_TIMESTAMP_COLUMN])
    mnt = mnt.dropna(subset=[WS])
    mt = config.MAINTENANCE_TYPE_COLUMN
    mnt = mnt.assign(
        _corr=(mnt[mt] == "reactive").astype(int), _prov=(mnt[mt] == "proactive").astype(int)
    )
    mnt_hour = (
        mnt.groupby([mc, WS], sort=False)
        .agg(_corr=("_corr", "sum"), _prov=("_prov", "sum"))
        .reset_index()
    )
    return inc_hour, mnt_hour


def build_gold_features(silver: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build the unified Gold feature table from the Silver frames (one row per machine-hour)."""
    mc = config.MACHINE_COLUMN

    # Spine: contiguous hourly telemetry per machine (window_start = the hour).
    sp = silver["telemetry"].copy()
    sp[WS] = _floor_hour(sp[config.TELEMETRY_TIMESTAMP_COLUMN])
    sp = (
        sp.dropna(subset=[WS])
        .drop_duplicates([mc, WS])
        .sort_values([mc, WS])
        .reset_index(drop=True)
    )

    inc_hour, mnt_hour = _per_hour_tables(silver, mc)
    df = sp.merge(inc_hour, on=[mc, WS], how="left").merge(mnt_hour, on=[mc, WS], how="left")
    hour_cols = ["_inc", "_sevmax", "_fail", *SIGNALS, "_corr", "_prov"]
    df[hour_cols] = df[hour_cols].fillna(0)
    df = df.sort_values([mc, WS]).reset_index(drop=True)
    g = df.groupby(mc, sort=False)

    feat: dict[str, pd.Series] = {}

    # --- Memory: rolling mean / max / std over each horizon ---
    for m in MEASURES:
        for h in MEM_H:
            feat[f"{m}_mean_{h}h"] = g[m].transform(
                lambda s, h=h: s.rolling(h, min_periods=1).mean()
            )
            feat[f"{m}_max_{h}h"] = g[m].transform(lambda s, h=h: s.rolling(h, min_periods=1).max())
            feat[f"{m}_std_{h}h"] = g[m].transform(lambda s, h=h: s.rolling(h, min_periods=2).std())

    # --- Trend: rolling OLS slope per hour ---
    for m in MEASURES:
        for h in TREND_H:
            feat[f"{m}_trend_{h}h"] = g[m].transform(
                lambda s, h=h: s.rolling(h, min_periods=2).apply(_slope, raw=True)
            )

    # --- Anomaly: z-score vs trailing 24h and vs the machine over all data ---
    for m in MEASURES:
        mean24 = g[m].transform(lambda s: s.rolling(24, min_periods=1).mean())
        std24 = g[m].transform(lambda s: s.rolling(24, min_periods=2).std())
        feat[f"{m}_z_24h"] = (df[m] - mean24) / std24
        feat[f"{m}_z_machine"] = (df[m] - g[m].transform("mean")) / g[m].transform("std")

    # --- Context: incidents (count + max severity per horizon) + recency ---
    for label, h in EVENT_H:
        feat[f"inc_count_{label}"] = g["_inc"].transform(
            lambda s, h=h: s.rolling(h, min_periods=1).sum()
        )
        feat[f"inc_sevmax_{label}"] = g["_sevmax"].transform(
            lambda s, h=h: s.rolling(h, min_periods=1).max()
        )
    feat["inc_hours_since_last"] = _hours_since_last(df, "_inc", mc)

    # --- Context: signal activations per horizon ---
    for s in SIGNALS:
        short = s.removeprefix("type_")
        for label, h in EVENT_H:
            feat[f"sig_{short}_count_{label}"] = g[s].transform(
                lambda x, h=h: x.rolling(h, min_periods=1).sum()
            )

    # --- Context: maintenance (corrective / proactive counts per horizon) + recency ---
    for label, d in MNT_D:
        w = d * 24
        feat[f"mnt_corr_count_{label}"] = g["_corr"].transform(
            lambda s, w=w: s.rolling(w, min_periods=1).sum()
        )
        feat[f"mnt_prov_count_{label}"] = g["_prov"].transform(
            lambda s, w=w: s.rolling(w, min_periods=1).sum()
        )
    feat["mnt_corr_days_since_last"] = _hours_since_last(df, "_corr", mc) / 24
    feat["mnt_prov_days_since_last"] = _hours_since_last(df, "_prov", mc) / 24

    # --- Labels: failure (severity >= 4) in the future window (censored at the series end) ---
    for label, h in LABEL_H:
        feat[f"label_failure_next_{label}"] = _future_failure(df, "_fail", mc, h)

    features = pd.DataFrame(feat, index=df.index)
    float_cols = features.select_dtypes("float").columns
    features[float_cols] = features[float_cols].round(4)

    ids = pd.DataFrame(
        {
            mc: df[mc],
            WS: df[WS],
            WE: df[WS] + pd.Timedelta(hours=1),
            "split_set": "train",
        }
    )
    gold = pd.concat([ids, features], axis=1)
    logger.info("Gold features built: %d rows x %d columns", len(gold), gold.shape[1])
    return gold


def read_silver(engine) -> dict[str, pd.DataFrame]:
    """Read the ``silver.*`` tables feeding Gold into the builder's input dict.

    The Gold-slot → table mapping comes from the single registry (``SourceSpec.gold_role`` /
    ``SourceSpec.table``), so adding a Gold-contributing source needs no change here.
    """
    from src.usecase.sources.registry import gold_sources

    return {
        role: pd.read_sql_table(spec.table, engine, schema=config.SILVER_SCHEMA)
        for role, spec in gold_sources().items()
    }


def build_gold_from_db(engine) -> pd.DataFrame:
    """Build ``gold.features`` from the ``silver.*`` DB tables (the Gold layer's source)."""
    return build_gold_features(read_silver(engine))
