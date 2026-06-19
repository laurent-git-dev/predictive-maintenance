"""Display helper: describe the Bronze -> Silver transformations per feature.

Display only — no processing happens here. The summary is **derived** from the Bronze
and Silver DataFrames plus the source's declarative :class:`ProcessingConfig`, so it
mirrors exactly what :func:`src.processing.pipeline.apply_processing` (and the source's
feature engineering) produced, without needing the runtime report.
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


def processing_summary_markdown(
    bronze_df: pd.DataFrame, silver_df: pd.DataFrame, processing: ProcessingConfig
) -> str:
    """Markdown describing, per feature, the transformations applied Bronze -> Silver."""
    lines: list[str] = []
    encoded_cols: set[str] = set()

    if processing.encode:
        lines += ["**Text → value (encoding)**", ""]
        for col, mapping in processing.encode.items():
            if col not in bronze_df.columns:
                continue
            new_col = f"{col}_code"
            encoded_cols.add(new_col)
            detail = (
                ", ".join(f"{k}→{v}" for k, v in mapping.items())
                if mapping
                else "auto category codes"
            )
            lines.append(f"- `{col}` → `{new_col}` ({detail})")
        lines.append("")

    if processing.impute:
        lines += ["**Imputation**", ""]
        for col, strategy in processing.impute.items():
            if col not in bronze_df.columns or col not in silver_df.columns:
                continue
            n_filled = int((bronze_df[col].isna() & silver_df[col].notna()).sum())
            lines.append(f"- `{col}` → {strategy} ({n_filled} value(s) filled)")
        lines.append("")

    if processing.outliers:
        lines += ["**Outliers (IQR clipping)**", ""]
        for col in processing.outliers:
            if col not in bronze_df.columns or col not in silver_df.columns:
                continue
            low, high = _iqr_bounds(bronze_df[col])
            bronze_num = pd.to_numeric(bronze_df[col], errors="coerce")
            n_clipped = int(((bronze_num < low) | (bronze_num > high)).sum())
            lines.append(
                f"- `{col}` → clipped to [{round(low, 3)}, {round(high, 3)}] "
                f"({n_clipped} value(s) clipped)"
            )
        lines.append("")

    derived = [c for c in silver_df.columns if c not in bronze_df.columns and c not in encoded_cols]
    if derived:
        lines += ["**Derived features (new in Silver)**", ""]
        lines += [f"- `{c}`" for c in derived]
        lines.append("")

    if not lines:
        return "_No transformation: Silver is identical to Bronze._"
    return "\n".join(lines).rstrip()
