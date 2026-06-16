"""Ingestion pipeline orchestration: load → anonymise → enrich.

The pipeline produces neither files nor plots: it returns an enriched DataFrame
and metrics. Persistence (CSV, PNG, report, registry) is handled by the CLI
script ``scripts/run_ingestion.py``, to keep the logic testable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from src import config
from src.ingestion.anonymizer import anonymize_incidents
from src.ingestion.loader import compute_quality_metrics, load_incidents

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Structured result of an ingestion pipeline run."""

    data: pd.DataFrame
    metrics_source: dict
    metrics_processed: dict
    anonymization_report: dict
    confidence_summary: dict = field(default_factory=dict)


def add_confidence_index(df: pd.DataFrame) -> pd.DataFrame:
    """Add the number of active signals and the confidence index per incident.

    The confidence index is ``n_active_signals / total_signals``: an incident
    corroborated by several simultaneous signals is deemed more reliable than
    one relying on a single isolated signal.
    """
    df = df.copy()
    present_signals = [c for c in config.SIGNAL_COLUMNS if c in df.columns]
    if not present_signals:
        logger.warning("No signal column found: confidence index skipped.")
        return df

    signals = df[present_signals].fillna(0).astype(int)
    df[config.N_SIGNALS_COLUMN] = signals.sum(axis=1)
    df[config.CONFIDENCE_COLUMN] = (df[config.N_SIGNALS_COLUMN] / len(present_signals)).round(4)
    return df


def run_pipeline(
    input_path, salt: str, pseudonym_length: int = config.DEFAULT_PSEUDONYM_LENGTH
) -> PipelineResult:
    """Run the full pipeline and return a :class:`PipelineResult`.

    Parameters
    ----------
    input_path : str | pathlib.Path
        Path to the source CSV.
    salt : str
        Secret anonymisation salt.
    pseudonym_length : int, optional
        Length of the ``operator_name`` pseudonym.
    """
    df_raw = load_incidents(input_path)
    metrics_source = compute_quality_metrics(df_raw)

    df_anon, anon_report = anonymize_incidents(df_raw, salt, pseudonym_length)
    df_final = add_confidence_index(df_anon)

    metrics_processed = compute_quality_metrics(df_final)

    confidence_summary = {}
    if config.CONFIDENCE_COLUMN in df_final.columns:
        confidence_summary = {
            "mean": round(float(df_final[config.CONFIDENCE_COLUMN].mean()), 4),
            "median": round(float(df_final[config.CONFIDENCE_COLUMN].median()), 4),
            "min": round(float(df_final[config.CONFIDENCE_COLUMN].min()), 4),
            "max": round(float(df_final[config.CONFIDENCE_COLUMN].max()), 4),
        }

    return PipelineResult(
        data=df_final,
        metrics_source=metrics_source,
        metrics_processed=metrics_processed,
        anonymization_report=anon_report,
        confidence_summary=confidence_summary,
    )
