"""Text -> value transformation: categorical encoding (mutualised, no I/O)."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def encode_categorical(
    df: pd.DataFrame, mappings: dict[str, dict | None]
) -> tuple[pd.DataFrame, dict]:
    """Encode text columns to numeric ``<col>_code`` columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Input data (a copy is returned; original columns are preserved).
    mappings : dict[str, dict | None]
        ``column -> explicit value map`` (e.g. ``{"matin": 0, "nuit": 2}``). If the
        value is ``None``, pandas categorical codes are used instead.

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        The enriched DataFrame and a report ``column -> {code_column, mapping}`` where
        ``mapping`` is the actual ``value -> code`` dictionary applied (including the
        auto-generated category codes), for JSON traceability.
    """
    df = df.copy()
    report: dict = {}
    for col, mapping in mappings.items():
        if col not in df.columns:
            continue
        new_col = f"{col}_code"
        if mapping:
            df[new_col] = df[col].map(mapping).astype("Int64")
            used = {str(k): int(v) for k, v in mapping.items()}
        else:
            categories = df[col].astype("category").cat.categories
            codes = df[col].astype("category").cat.codes
            df[new_col] = codes.replace(-1, pd.NA).astype("Int64")
            used = {str(value): int(i) for i, value in enumerate(categories)}
        report[col] = {"code_column": new_col, "mapping": used}
    if report:
        logger.info("Encoded categorical columns: %s", list(report))
    return df, report
