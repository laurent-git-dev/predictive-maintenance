"""Display helper: describe the Bronze -> Silver transformation **per feature**.

Display only — no processing happens here. Everything is **derived** from the Bronze and
Silver DataFrames plus the source's declarative :class:`ProcessingConfig`, so it mirrors
exactly what :func:`src.processing.pipeline.apply_processing` (and the source's feature
engineering) produced, without needing the runtime report.
"""

from __future__ import annotations

import pandas as pd

from src.processing.pipeline import ProcessingConfig


def _iqr_bounds(series: pd.Series, k: float = 1.5) -> tuple[float, float]:
    """IQR fences ``[Q1 - k*IQR, Q3 + k*IQR]`` (same rule as treat_outliers)."""
    num = pd.to_numeric(series, errors="coerce")
    q1, q3 = num.quantile(0.25), num.quantile(0.75)
    iqr = q3 - q1
    return float(q1 - k * iqr), float(q3 + k * iqr)


def _feature_treatment(
    col: str, bronze_df: pd.DataFrame, silver_df: pd.DataFrame, processing: ProcessingConfig
) -> list[str]:
    """Bullet lines describing the Bronze -> Silver treatment applied to one feature."""
    bullets: list[str] = []
    in_bronze = col in bronze_df.columns
    merged = not in_bronze

    if col in processing.dedup.get("keys", []):
        bullets.append(f"deduplication key (strategy: {processing.dedup.get('strategy')})")
    if merged:
        bullets.append("merged from the machine dimension (star schema)")
    if col in processing.encode:
        mapping = processing.encode[col]
        detail = (
            ", ".join(f"{k}→{v}" for k, v in mapping.items()) if mapping else "auto category codes"
        )
        bullets.append(f"text → value → `{col}_code` ({detail}); traced in `text_encodings.json`")
    if col in processing.impute and in_bronze and col in silver_df.columns:
        n_filled = int((bronze_df[col].isna() & silver_df[col].notna()).sum())
        bullets.append(f"imputation: {processing.impute[col]} ({n_filled} value(s) filled)")
    if col in processing.outliers and in_bronze:
        low, high = _iqr_bounds(bronze_df[col])
        bronze_num = pd.to_numeric(bronze_df[col], errors="coerce")
        n_clipped = int(((bronze_num < low) | (bronze_num > high)).sum())
        bullets.append(
            f"outliers: IQR clip to [{round(low, 3)}, {round(high, 3)}] ({n_clipped} clipped)"
        )
    if col in processing.normalize:
        bullets.append(f"normalization: {processing.normalize[col]} → `{col}_norm`")

    if not bullets:
        bullets.append(
            "new in Silver (feature engineering)" if merged else "kept as-is (no transformation)"
        )
    return bullets


def per_feature_processing_markdown(
    bronze_df: pd.DataFrame,
    silver_df: pd.DataFrame,
    processing: ProcessingConfig,
    prefix: str = "2",
) -> str:
    """Numbered per-feature markdown (``##### <prefix>.<i> <feature>``) of the treatment.

    Features are the Silver columns excluding the generated ``_code`` / ``_norm`` outputs
    (those are mentioned under their source feature).
    """
    base_cols = [c for c in silver_df.columns if not (c.endswith("_code") or c.endswith("_norm"))]
    lines: list[str] = []
    for i, col in enumerate(base_cols, start=1):
        lines.append(f"##### {prefix}.{i} {col}")
        lines += [
            f"- {bullet}" for bullet in _feature_treatment(col, bronze_df, silver_df, processing)
        ]
        lines.append("")
    return "\n".join(lines).rstrip()
