"""Declarative processing pipeline: apply transformation/imputation/outliers.

Anonymisation is intentionally NOT applied here: for PII sources it is applied at
ingestion (so no artifact ever contains PII). This stage prepares the DB-ready
dataset from data that is already understood/anonymised.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from src.processing.imputation import impute
from src.processing.outliers import treat_outliers
from src.processing.transformation import encode_categorical

logger = logging.getLogger(__name__)


@dataclass
class ProcessingConfig:
    """Declarative processing steps for one source.

    Attributes
    ----------
    encode : dict[str, dict | None]
        ``column -> value map`` (or ``None`` for automatic category codes).
    impute : dict[str, str]
        ``column -> strategy`` (``median`` | ``mean`` | ``mode``).
    outliers : list[str]
        Numeric columns to winsorize with the IQR rule.
    """

    encode: dict = field(default_factory=dict)
    impute: dict = field(default_factory=dict)
    outliers: list = field(default_factory=list)


def apply_processing(df: pd.DataFrame, config: ProcessingConfig) -> tuple[pd.DataFrame, dict]:
    """Apply the configured processing steps and return ``(df, report)``."""
    report: dict = {}
    if config.encode:
        df, report["encode"] = encode_categorical(df, config.encode)
    if config.impute:
        df, report["impute"] = impute(df, config.impute)
    if config.outliers:
        df, report["outliers"] = treat_outliers(df, config.outliers)
    return df, report
