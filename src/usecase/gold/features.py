"""Unified Gold feature table — one row per ``(machine_id, 1-hour window)``.

Built from the three (clean) Silver frames into a single training-ready table. The decision
instant of a row is ``t = window_end``: **backward** windows (memory / trend / anomaly /
context) look up to and **including** the current hour; **labels** look **strictly after**
``t``. A *failure* is an incident of **severity >= 4**.

Telemetry is a contiguous hourly grid per machine, so the ``-Nh`` windows are exact
(count-based). Feature groups: identifiers, memory (rolling mean/max/std), trend (rolling
OLS slope), anomaly (z vs 24h and vs the machine's history **so far** — expanding, causal),
context (incidents / signals / maintenance), recurrence (past failures), machine (static
dimension + age), load (utilisation vs capacity), calendar (cyclical) and labels.
``split_set`` (train/val/test) is assigned per ``params.yaml`` (temporal by default). All
features are strictly causal (≤ ``t``); no statistic peeks at the future.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import yaml

from src import config
from src.framework.timeutils import to_naive_hour

logger = logging.getLogger(__name__)

# Gold spec defaults (reproduce the reference table). Overridable via params.yaml → gold.*
_DEFAULT_SPLIT: dict = {"method": "temporal", "train_frac": 0.7, "val_frac": 0.15}
_GOLD_DEFAULTS = {
    "failure_severity_min": 4,
    "memory_horizons_h": [2, 3, 4, 6, 12, 24, 48],
    "trend_horizons_h": [2, 3, 4, 5, 6],
    "event_horizons": {"6h": 6, "12h": 12, "24h": 24, "48h": 48, "7d": 168},
    "maintenance_windows_d": {"5d": 5, "10d": 10, "20d": 20, "30d": 30, "60d": 60},
    "label_horizons": {"6h": 6, "12h": 12, "24h": 24, "48h": 48},
    "split": _DEFAULT_SPLIT,
    "baseline_hours": 168,  # healthy-baseline window per machine (drift features)
    "failure_refractory_h": 0,  # >0: only failures spaced >this count as a new onset (labels)
}


def load_gold_params() -> dict:
    """Read the Gold spec from ``params.yaml`` (``gold`` section), filling missing keys."""
    params = dict(_GOLD_DEFAULTS)
    path = config.PROJECT_ROOT / "params.yaml"
    if path.exists():
        loaded = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("gold") or {}
        params.update(loaded)
    return params


_P = load_gold_params()
FAILURE_SEVERITY_MIN = int(_P["failure_severity_min"])  # incident severity >= this = failure
MEASURES = list(config.TELEMETRY_PARAM_COLUMNS)  # 5 telemetry measures (incl. pieces_produced)
SENSOR_MEASURES = [m for m in MEASURES if m != config.TELEMETRY_PIECES_COLUMN]  # 4 physical sensors
SIGNALS = list(config.SIGNAL_COLUMNS)  # 9 type_* signals
BASELINE_HOURS = int(_P.get("baseline_hours", 168))  # healthy-baseline window (drift features)
FAILURE_REFRACTORY_H = int(_P.get("failure_refractory_h", 0))  # 0 = every failure hour is an onset
MEM_H = list(_P["memory_horizons_h"])  # memory horizons (hours)
TREND_H = list(_P["trend_horizons_h"])  # trend horizons (hours)
EVENT_H = list(_P["event_horizons"].items())  # incident/signal horizons (label, hours)
MNT_D = list(_P["maintenance_windows_d"].items())  # maintenance windows (label, days)
LABEL_H = list(_P["label_horizons"].items())  # label horizons (label, hours)
SPLIT = {**_DEFAULT_SPLIT, **(_P.get("split") or {})}  # train/val/test policy
WS, WE = "window_start", "window_end"

# Representative subset for the layer profiling (the full table is ~240 columns).
FEATURES_NUMERIC = [
    *[f"{m}_mean_24h" for m in MEASURES],
    *[f"{m}_z_hist" for m in MEASURES],
    "utilization",
    "machine_age_years",
    "inc_hours_since_last",
    "fail_hours_since_last",
    "mnt_corr_days_since_last",
]
FEATURES_COUNT = [
    "label_failure_next_6h",
    "label_failure_next_24h",
    "label_failure_next_48h",
    "fail_count_24h",
    "over_capacity_flag",
    "is_weekend",
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


def _time_to_failure(df: pd.DataFrame, hour_flag: str, mc: str) -> pd.Series:
    """Hours until the next ``hour_flag`` event strictly after ``t`` (NaN if none observed).

    Regression / survival target. NaN = right-censored (no future failure in the series).
    The hourly grid is contiguous per machine, so a position delta equals hours.
    """
    out = pd.Series(np.nan, index=df.index, dtype="float64")
    for _, idx in df.groupby(mc, sort=False).groups.items():
        sub = df.loc[idx].sort_values(WS)
        f = (pd.to_numeric(sub[hour_flag], errors="coerce") > 0).to_numpy()
        fpos = np.flatnonzero(f)
        n = len(f)
        vals = np.full(n, np.nan)
        if len(fpos):
            nxt = np.searchsorted(fpos, np.arange(n), side="right")  # first failure pos > i
            has = nxt < len(fpos)
            vals[has] = fpos[nxt[has]] - np.arange(n)[has]
        out.loc[sub.index] = vals
    return out


def _per_hour_tables(silver: dict, mc: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate incident & maintenance events to per-(machine, hour) helper columns."""
    inc = silver["incidents"].copy()
    inc[WS] = _floor_hour(
        inc[config.DATE_COLUMN].astype(str) + " " + inc[config.TIME_COLUMN].astype(str)
    )
    inc = inc.dropna(subset=[WS])
    sev = pd.to_numeric(inc[config.SEVERITY_COLUMN], errors="coerce")
    inc = inc.assign(_sev=sev, _fail=(sev >= FAILURE_SEVERITY_MIN).astype(int))
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


def _machine_dimension(silver: dict, mc: str) -> tuple[pd.DataFrame, list[str]]:
    """Static per-machine attributes (the dimension denormalised into silver.maintenance)."""
    mnt = silver["maintenance"]
    candidates = [
        f"{config.MACHINE_CRITICALITY_COLUMN}_code",
        f"{config.MACHINE_MODEL_COLUMN}_code",
        f"{config.MACHINE_LINE_COLUMN}_code",
        f"{config.MACHINE_LOCATION_COLUMN}_code",
        config.MACHINE_MAX_DAILY_COLUMN,
        config.MACHINE_MAX_HOURLY_COLUMN,
        config.MACHINE_COMMISSIONING_COLUMN,
    ]
    present = [c for c in candidates if c in mnt.columns]
    dim = mnt[[mc, *present]].drop_duplicates(mc).reset_index(drop=True)
    return dim, present


def _calendar_features(ws: pd.Series) -> dict[str, pd.Series]:
    """Cyclical calendar features from the window start (depend only on ``t``; no leakage)."""
    hour, dow = ws.dt.hour, ws.dt.dayofweek
    two_pi = 2 * np.pi
    return {
        "hour_sin": np.sin(two_pi * hour / 24),
        "hour_cos": np.cos(two_pi * hour / 24),
        "dow_sin": np.sin(two_pi * dow / 7),
        "dow_cos": np.cos(two_pi * dow / 7),
        "is_weekend": (dow >= 5).astype("int64"),
    }


def _assign_split(df: pd.DataFrame, mc: str, split: dict) -> pd.Series:
    """Assign train/val/test. ``temporal`` = global cut on time (test = most recent period);
    ``by_machine`` = hold out whole machines; ``none`` = all train."""
    method = split.get("method", "temporal")
    train_frac = float(split.get("train_frac", 0.7))
    val_frac = float(split.get("val_frac", 0.15))
    if method == "none":
        return pd.Series("train", index=df.index)
    if method == "by_machine":
        machines = sorted(df[mc].unique())
        n = len(machines)
        n_train = max(1, round(train_frac * n))
        n_val = round(val_frac * n)
        assign = {
            m: ("train" if i < n_train else "val" if i < n_train + n_val else "test")
            for i, m in enumerate(machines)
        }
        return df[mc].map(assign)
    t_train = df[WS].quantile(train_frac)
    t_val = df[WS].quantile(train_frac + val_frac)
    return pd.Series(
        np.where(df[WS] <= t_train, "train", np.where(df[WS] <= t_val, "val", "test")),
        index=df.index,
    )


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

    dim, dim_cols = _machine_dimension(silver, mc)  # static machine attributes (broadcast)
    df = df.merge(dim, on=mc, how="left")
    df = df.sort_values([mc, WS]).reset_index(drop=True)
    g = df.groupby(mc, sort=False)

    # Label event: every failure hour (default), or only failure ONSETs spaced by a refractory
    # period (failure_refractory_h > 0 -> predict new episodes rather than any failure hour).
    if FAILURE_REFRACTORY_H > 0:
        prior = (
            g["_fail"]
            .transform(lambda s: s.rolling(FAILURE_REFRACTORY_H, min_periods=1).sum().shift(1))
            .fillna(0)
        )
        df["_fail_label"] = ((df["_fail"] > 0) & (prior == 0)).astype("int64")
    else:
        df["_fail_label"] = df["_fail"].astype("int64")

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

    # --- Anomaly: z vs trailing 24h, and vs the machine's history SO FAR (causal: expanding) ---
    for m in MEASURES:
        mean24 = g[m].transform(lambda s: s.rolling(24, min_periods=1).mean())
        std24 = g[m].transform(lambda s: s.rolling(24, min_periods=2).std())
        feat[f"{m}_z_24h"] = (df[m] - mean24) / std24
        mean_hist = g[m].transform(lambda s: s.expanding(min_periods=2).mean())
        std_hist = g[m].transform(lambda s: s.expanding(min_periods=2).std())
        feat[f"{m}_z_hist"] = (df[m] - mean_hist) / std_hist

    # --- Context: incidents (count + max severity per horizon) + recency ---
    for label, h in EVENT_H:
        feat[f"inc_count_{label}"] = g["_inc"].transform(
            lambda s, h=h: s.rolling(h, min_periods=1).sum()
        )
        feat[f"inc_sevmax_{label}"] = g["_sevmax"].transform(
            lambda s, h=h: s.rolling(h, min_periods=1).max()
        )
    feat["inc_hours_since_last"] = _hours_since_last(df, "_inc", mc)

    # --- Context: past FAILURES (severity >= threshold) — recurrence is strongly predictive ---
    for label, h in EVENT_H:
        feat[f"fail_count_{label}"] = g["_fail"].transform(
            lambda s, h=h: s.rolling(h, min_periods=1).sum()
        )
    feat["fail_count_cum"] = g["_fail"].cumsum()  # all past failures up to & incl. t
    feat["fail_hours_since_last"] = _hours_since_last(df, "_fail", mc)
    feat["failure_now"] = df["_fail"].astype("int64")  # flag to exclude ongoing-failure rows

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

    # --- Machine context: static dimension attributes (broadcast per machine) + age at t ---
    for col in dim_cols:
        if col != config.MACHINE_COMMISSIONING_COLUMN:
            feat[f"machine_{col}"] = df[col]
    if config.MACHINE_COMMISSIONING_COLUMN in dim_cols:
        comm = pd.to_datetime(df[config.MACHINE_COMMISSIONING_COLUMN], errors="coerce")
        feat["machine_age_years"] = (df[WS] - comm).dt.total_seconds() / (365.25 * 24 * 3600)

    # --- Load: production vs the machine's hourly capacity (current hour + trailing 24h) ---
    if config.MACHINE_MAX_HOURLY_COLUMN in dim_cols:
        cap = pd.to_numeric(df[config.MACHINE_MAX_HOURLY_COLUMN], errors="coerce")
        pieces = pd.to_numeric(df[config.TELEMETRY_PIECES_COLUMN], errors="coerce")
        util = pieces / cap.where(cap > 0)
        feat["utilization"] = util
        feat["over_capacity_flag"] = (util > 1).astype("int64")
        feat["utilization_mean_24h"] = util.groupby(df[mc]).transform(
            lambda s: s.rolling(24, min_periods=1).mean()
        )

    # --- Calendar: cyclical time-of-day / day-of-week (depends only on t) ---
    feat.update(_calendar_features(df[WS]))

    # --- Physics / interactions (current hour; co-anomaly uses the causal 24h z-scores) ---
    volt = pd.to_numeric(df["voltage_mean_v"], errors="coerce")
    rpm = pd.to_numeric(df["rotation_mean_rpm"], errors="coerce")
    temp = pd.to_numeric(df["temperature_c"], errors="coerce")
    press = pd.to_numeric(df["pressure_bar"], errors="coerce")
    pieces = pd.to_numeric(df[config.TELEMETRY_PIECES_COLUMN], errors="coerce")
    power = volt * rpm
    feat["power_proxy"] = power  # electrical/mechanical load proxy
    feat["power_proxy_mean_24h"] = power.groupby(df[mc]).transform(
        lambda s: s.rolling(24, min_periods=1).mean()
    )
    feat["temp_pressure_ratio"] = temp / press.where(press != 0)
    feat["efficiency_pieces_per_krpm"] = pieces / (rpm / 1000).where(rpm != 0)
    z24 = pd.DataFrame({m: feat[f"{m}_z_24h"] for m in MEASURES})
    feat["co_anomaly_24h"] = (z24.abs() > 3).sum(axis=1).astype("int64")  # multi-sensor anomaly

    # --- Drift vs the machine's healthy baseline (median of its first BASELINE_HOURS hours) ---
    # Causal: emitted only once the baseline window is fully in the past (NaN before).
    pos = g.cumcount()
    for m in SENSOR_MEASURES:
        base = g[m].transform(lambda s: s.head(BASELINE_HOURS).median())
        feat[f"{m}_drift_baseline"] = (df[m] - base).where(pos >= BASELINE_HOURS)

    # --- Data coverage: how much of the recent window was interpolated (feature confidence) ---
    interp = config.TELEMETRY_INTERPOLATED_COLUMN
    if interp in df.columns:
        flag = pd.to_numeric(df[interp], errors="coerce").fillna(0)
        feat["interpolated_now"] = flag.astype("int64")
        feat["interp_frac_24h"] = flag.groupby(df[mc]).transform(
            lambda s: s.rolling(24, min_periods=1).mean()
        )
        feat["hours_since_real_obs"] = _hours_since_last(df.assign(_real=1 - flag), "_real", mc)

    # --- Labels: failure (severity >= threshold) in the future window (censored at series end) ---
    for label, h in LABEL_H:
        feat[f"label_failure_next_{label}"] = _future_failure(df, "_fail_label", mc, h)
    # Time-to-failure (regression / survival): hours to the next failure; censored -> NaN.
    feat["label_ttf_hours"] = _time_to_failure(df, "_fail_label", mc)
    feat["label_ttf_censored"] = feat["label_ttf_hours"].isna().astype("int64")

    features = pd.DataFrame(feat, index=df.index)
    float_cols = features.select_dtypes("float").columns
    features[float_cols] = features[float_cols].round(4)

    ids = pd.DataFrame(
        {
            mc: df[mc],
            WS: df[WS],
            WE: df[WS] + pd.Timedelta(hours=1),
            "split_set": _assign_split(df, mc, SPLIT),
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
