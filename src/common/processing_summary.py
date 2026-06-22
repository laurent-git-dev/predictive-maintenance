"""Display helper: describe the Bronze -> Silver transformation **per feature**.

Display only — no processing happens here. Everything is **derived** from the Bronze and
Silver DataFrames plus the source's declarative :class:`ProcessingConfig`, so it mirrors
exactly what :func:`src.processing.pipeline.apply_processing` (and the source's feature
engineering) produced, without needing the runtime report.

Only features that were **actually transformed** (encoded, imputed, winsorized, normalized,
deduplicated) or **created** during processing are documented; columns carried over
unchanged are summarised in a single trailing line. Each transformation is described with
*what* was done, *why*, and — whenever possible — a concrete *example* read from the data.
Features newly created in this step are flagged ``(NEW)`` (in purple) next to their title.
"""

from __future__ import annotations

import pandas as pd

from src import config
from src.common.profiling import new_feature_badge
from src.processing.pipeline import ProcessingConfig

# ── New Silver features built by feature engineering: (what, why) ────────────────────────
_ENGINEERED_NOTES: dict[str, tuple[str, str]] = {
    config.DATETIME_COLUMN: (
        "combines `date` + `time` into a single timestamp",
        "enables fine-grained (hour-level) temporal analysis, impossible with the two "
        "separate text columns",
    ),
    "hour": (
        "hour of day (0-23) extracted from the event timestamp",
        "exposes daily seasonality (shift effects) as a usable numeric predictor",
    ),
    "weekday": (
        "day of week (0=Monday … 6=Sunday) extracted from the event timestamp",
        "captures weekly patterns (weekday vs weekend regimes)",
    ),
    "month": (
        "calendar month (1-12) extracted from the event timestamp",
        "captures yearly seasonality",
    ),
    "is_weekend": (
        "1 when the event falls on Saturday/Sunday, else 0",
        "a compact weekend indicator for models that do not need the full weekday",
    ),
    "comment_pii_flag": (
        "1 when the free-text `comment` holds content, else 0",
        "flags rows needing manual PII review without carrying the raw text downstream",
    ),
    "production_stop_flag": (
        "1 when the comment mentions a production-stop marker (line stop / emergency cut-off)",
        "isolates the high-impact incidents that halted production",
    ),
    config.N_SIGNALS_COLUMN: (
        "count of active `type_*` signals on the incident",
        "more simultaneous signals describe a richer, better-corroborated incident",
    ),
    config.CONFIDENCE_COLUMN: (
        "`n_active_signals / total signals` (0-1)",
        "an incident corroborated by several signals is deemed more reliable than one "
        "relying on a single isolated signal",
    ),
    "over_capacity_flag": (
        "1 when `pieces_produced` exceeds the machine's declared hourly capacity",
        "flags physically implausible readings (above the referential maximum)",
    ),
    "machine_age_years": (
        "machine age at maintenance time = (`maintenance_at` - `commissioning_date`) / 365.25",
        "wear correlates with age, giving a continuous predictor of failures",
    ),
}

# ── Silver columns merged in from the machine dimension (star schema): what they carry ───
_MERGED_NOTES: dict[str, str] = {
    config.MACHINE_CRITICALITY_COLUMN: "the machine's business criticality (LOW/MEDIUM/HIGH)",
    config.MACHINE_LINE_COLUMN: "the production line the machine belongs to",
    config.MACHINE_LOCATION_COLUMN: "the workshop where the machine is installed",
    config.MACHINE_MODEL_COLUMN: "the machine model",
    config.MACHINE_COMMISSIONING_COLUMN: "the machine's commissioning date",
    config.MACHINE_MAX_DAILY_COLUMN: "the machine's maximum daily production capacity",
    config.MACHINE_MAX_HOURLY_COLUMN: "the machine's maximum hourly production capacity",
}


def _fmt(value) -> str:
    """Compact, human-readable rendering of a single cell value."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return "NA"
    if isinstance(value, float):
        return f"{round(value, 3):g}"
    return str(value)


def _iqr_bounds(series: pd.Series, k: float = 1.5) -> tuple[float, float]:
    """IQR fences ``[Q1 - k*IQR, Q3 + k*IQR]`` (same rule as treat_outliers)."""
    num = pd.to_numeric(series, errors="coerce")
    q1, q3 = num.quantile(0.25), num.quantile(0.75)
    iqr = q3 - q1
    return float(q1 - k * iqr), float(q3 + k * iqr)


def _encode_bullet(col: str, silver_df: pd.DataFrame, mapping: dict | None) -> str:
    """Describe the text -> value encoding applied to ``col`` (with an example)."""
    code_col = f"{col}_code"
    if mapping:
        pairs = [(str(k), int(v)) for k, v in mapping.items()]
        kind = "explicit ordered mapping (preserves a meaningful order)"
    elif code_col in silver_df.columns:
        seen = silver_df[[col, code_col]].dropna().drop_duplicates().sort_values(code_col)
        pairs = [(str(v), int(c)) for v, c in seen.itertuples(index=False, name=None)]
        kind = "nominal categories mapped to integer codes (alphabetical order)"
    else:
        pairs = []
        kind = "category codes"
    shown = ", ".join(f"`{v}` -> `{c}`" for v, c in pairs[:4])
    if len(pairs) > 4:
        shown += f", … ({len(pairs)} categories)"
    return (
        f"**Text -> value encoding** into a new numeric column `{code_col}` ({kind}). "
        f"_Why:_ models require numeric inputs; the original text is kept for readability and "
        f"the full map is traced in `text_encodings.json`."
        + (f" _Example:_ {shown}." if shown else "")
    )


def _impute_bullet(col: str, bronze_df: pd.DataFrame, strategy: str) -> str | None:
    """Describe imputation of ``col`` (``None`` if there was nothing to fill)."""
    n_missing = int(bronze_df[col].isna().sum())
    if n_missing == 0:
        return None
    num = pd.to_numeric(bronze_df[col], errors="coerce")
    fill = {"median": num.median, "mean": num.mean}.get(strategy)
    fill_value = _fmt(fill()) if fill else _fmt(bronze_df[col].mode(dropna=True).iloc[0])
    return (
        f"**Imputation** ({strategy}): filled {n_missing} missing value(s). "
        f"_Why:_ missing values would break numeric aggregations and model training. "
        f"_Example:_ the {strategy} (`{fill_value}`) was substituted for each gap."
    )


def _interpolate_bullet(col: str, bronze_df: pd.DataFrame, interp: dict) -> str | None:
    """Describe per-group time interpolation of ``col`` (``None`` if nothing was missing)."""
    n_missing = int(bronze_df[col].isna().sum())
    if n_missing == 0:
        return None
    group, time = interp.get("group"), interp.get("time")
    return (
        f"**Imputation by time interpolation** (per `{group}`, ordered by `{time}`): filled "
        f"{n_missing} missing reading(s) by interpolating over time within each machine "
        f"(leading/trailing gaps closed by forward/backward fill). _Why:_ telemetry is an "
        f"hourly per-machine series — a neighbour-in-time estimate respects the signal "
        f"dynamics, whereas a global median injects an artificial spike at the median value. "
        f"_Example:_ a gap between two hourly readings is filled by their time-weighted value."
    )


def _outlier_bullet(col: str, bronze_df: pd.DataFrame) -> str | None:
    """Describe IQR winsorization of ``col`` (``None`` if nothing was out of bounds)."""
    low, high = _iqr_bounds(bronze_df[col])
    num = pd.to_numeric(bronze_df[col], errors="coerce")
    extreme = num[(num < low) | (num > high)]
    n_clipped = int(extreme.size)
    if n_clipped == 0:
        return None
    sample = extreme.iloc[(extreme - extreme.median()).abs().argmax()]
    bound = high if sample > high else low
    return (
        f"**Outliers** (IQR rule, k=1.5): clipped {n_clipped} reading(s) to "
        f"[`{round(low, 3):g}`, `{round(high, 3):g}`]. "
        f"_Why:_ extreme sensor spikes would distort the mean and the normalization scale; "
        f"winsorizing caps them at the IQR fence instead of dropping the row. "
        f"_Example:_ `{_fmt(sample)}` -> `{round(bound, 3):g}`."
    )


def _normalize_bullet(col: str, silver_df: pd.DataFrame, method: str) -> str:
    """Describe normalization of ``col`` -> ``<col>_norm`` (with an example)."""
    norm_col = f"{col}_norm"
    why = {
        "zscore": "centres to mean 0 / std 1 so features on different scales are comparable",
        "minmax": "rescales to [0, 1] so features on different scales are comparable",
    }.get(method, "rescales the feature")
    example = ""
    if norm_col in silver_df.columns:
        paired = silver_df[[col, norm_col]].dropna()
        if not paired.empty:
            v, n = paired.iloc[0]
            example = f" _Example:_ `{_fmt(v)}` -> `{_fmt(n)}`."
    return (
        f"**Normalization** ({method}) into a new column `{norm_col}`. _Why:_ {why} for "
        f"distance-based and gradient-based models." + example
    )


def _new_feature_bullet(col: str, bronze_df: pd.DataFrame, silver_df: pd.DataFrame) -> str:
    """Lead bullet for a feature created during processing (engineered or merged)."""
    series = silver_df[col]
    if col in _MERGED_NOTES:
        example = ""
        if config.MACHINE_COLUMN in silver_df.columns:
            row = silver_df[[config.MACHINE_COLUMN, col]].dropna()
            if not row.empty:
                machine, value = row.iloc[0]
                example = f" _Example:_ `{machine}` -> `{_fmt(value)}`."
        return (
            f"**Merged from the machine dimension** (star schema, joined on "
            f"`{config.MACHINE_COLUMN}`): carries {_MERGED_NOTES[col]}. "
            f"_Why:_ denormalising the dimension onto every maintenance row lets each event "
            f"be analysed with its machine context, without a separate join.{example}"
        )
    what, why = _ENGINEERED_NOTES.get(
        col, ("derived during Silver feature engineering", "adds analysis-ready signal")
    )
    values = series.dropna()
    example = ""
    if not values.empty:
        uniques = set(pd.unique(values))
        if uniques <= {0, 1}:
            n_set = int((values == 1).sum())
            example = f" _Example:_ set for {n_set} of {len(series)} rows."
        elif pd.api.types.is_numeric_dtype(values):
            example = f" _Example:_ ranges `{_fmt(values.min())}` … `{_fmt(values.max())}`."
        else:
            example = f" _Example:_ `{_fmt(values.iloc[0])}`."
    return f"**Created in this step**: {what}. _Why:_ {why}.{example}"


def _feature_treatment(
    col: str, bronze_df: pd.DataFrame, silver_df: pd.DataFrame, processing: ProcessingConfig
) -> tuple[list[str], bool]:
    """Bullets describing the treatment of one feature, and whether it is newly created.

    Returns ``([], is_new=False)`` for columns carried over unchanged (so the caller can
    skip them).
    """
    in_bronze = col in bronze_df.columns
    is_new = not in_bronze
    bullets: list[str] = []

    if is_new:
        bullets.append(_new_feature_bullet(col, bronze_df, silver_df))

    if col in processing.dedup.get("keys", []):
        strat = processing.dedup.get("strategy", "first")
        how = (
            "merged by averaging the numeric measures"
            if strat == "mean"
            else f"kept the {strat} row of each group"
        )
        keys = ", ".join(f"`{k}`" for k in processing.dedup["keys"])
        bullets.append(
            f"**Deduplication key**: rows sharing the same ({keys}) were collapsed — {how} — "
            f"reducing {len(bronze_df)} -> {len(silver_df)} rows "
            f"({len(bronze_df) - len(silver_df)} removed). _Why:_ reconciles conflicting "
            f"duplicate readings into one record per logical key."
        )
    interp = processing.interpolate or {}
    if col in interp.get("columns", []) and in_bronze:
        bullet = _interpolate_bullet(col, bronze_df, interp)
        if bullet:
            bullets.append(bullet)
    if col in processing.encode:
        bullets.append(_encode_bullet(col, silver_df, processing.encode[col]))
    if col in processing.impute and in_bronze:
        bullet = _impute_bullet(col, bronze_df, processing.impute[col])
        if bullet:
            bullets.append(bullet)
    if col in processing.outliers and in_bronze:
        bullet = _outlier_bullet(col, bronze_df)
        if bullet:
            bullets.append(bullet)
    if col in processing.normalize:
        bullets.append(_normalize_bullet(col, silver_df, processing.normalize[col]))

    return bullets, is_new


def per_feature_processing_markdown(
    bronze_df: pd.DataFrame,
    silver_df: pd.DataFrame,
    processing: ProcessingConfig,
    prefix: str = "2",
) -> str:
    """Numbered per-feature markdown (``##### <prefix>.<i> <feature>``) of the treatment.

    Only transformed or newly created features are listed; the generated ``_code`` / ``_norm``
    outputs are described under their source feature. Columns carried over unchanged are
    summarised in a single trailing line (transparency: nothing is silently dropped).
    """
    base_cols = [c for c in silver_df.columns if not (c.endswith("_code") or c.endswith("_norm"))]

    lines: list[str] = []
    unchanged: list[str] = []
    shown = 0
    for col in base_cols:
        bullets, is_new = _feature_treatment(col, bronze_df, silver_df, processing)
        if not bullets:
            unchanged.append(col)
            continue
        shown += 1
        lines.append(f"##### {prefix}.{shown} {col}{new_feature_badge(is_new)}")
        lines += [f"- {bullet}" for bullet in bullets]
        lines.append("")

    if unchanged:
        listed = ", ".join(f"`{c}`" for c in unchanged)
        lines.append(f"_{len(unchanged)} feature(s) carried over unchanged (not shown): {listed}._")
    return "\n".join(lines).rstrip()
