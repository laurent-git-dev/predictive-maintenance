"""Silver refinement: from the ingested ``bronze.*`` tables to the cleaned ``silver.*`` tables.

Flow per source: read ``bronze.<table>`` (with the Bronze ``parse_ok`` / ``parse_reason``
flags) → apply the **reject policy** → run the existing treatments (``apply_processing`` +
dimension merge) → return the Silver frame, the treatment report and ingestion stats.

Reject policy: a flagged row whose anomalies are **only** ``duplicate`` / ``missing`` is
**kept** (deduplication and imputation/interpolation correct it); a row carrying any other
anomaly (``type`` / ``domain`` / ``format`` / ``range`` / ``invalid``) is **rejected** (dropped).
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.engine import Engine

from src import config
from src.framework.ingestion.validate import PARSE_OK, PARSE_REASON
from src.usecase.sources.registry import SOURCE_SPECS

logger = logging.getLogger(__name__)

CORRECTABLE = {"duplicate", "missing"}  # anomalies the existing treatments can fix
_SPECS = {s.name: s for s in SOURCE_SPECS}


def read_bronze_table(table: str, engine: Engine) -> pd.DataFrame:
    """Read ``bronze.<table>`` from the database (drop the surrogate ``id``)."""
    df = pd.read_sql_table(table, engine, schema=config.BRONZE_SCHEMA)
    return df.drop(columns=["id"], errors="ignore")


def _is_correctable(reason: str) -> bool:
    """True if every anomaly token of ``parse_reason`` is correctable by a treatment."""
    kinds = [tok.split(":", 1)[0] for tok in str(reason).split(";") if tok]
    return all(k in CORRECTABLE for k in kinds)


def split_rejected(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into (kept, rejected) per the reject policy. ``kept`` excludes the parse columns."""
    if PARSE_OK not in df.columns:
        return df, df.iloc[0:0]
    keep_mask = df[PARSE_OK].astype(bool) | df[PARSE_REASON].map(_is_correctable)
    kept = df[keep_mask].drop(columns=[PARSE_OK, PARSE_REASON], errors="ignore")
    rejected = df[~keep_mask]
    return kept.reset_index(drop=True), rejected.reset_index(drop=True)


def _modifications(report: dict) -> dict:
    """Count the modifications applied by the treatments (from the apply_processing report)."""
    mods: dict[str, int] = {}
    if report.get("dedup"):
        mods["rows_deduplicated"] = int(report["dedup"].get("n_removed", 0))
    if report.get("interpolate"):
        mods["values_interpolated"] = int(
            sum(v.get("n_filled", 0) for v in report["interpolate"].values())
        )
    if report.get("impute"):
        mods["values_imputed"] = int(sum(v.get("n_filled", 0) for v in report["impute"].values()))
    if report.get("outliers"):
        mods["outliers_clipped"] = int(
            sum(v.get("n_clipped", 0) for v in report["outliers"].values())
        )
    if report.get("encode"):
        mods["columns_encoded"] = len(report["encode"])
    if report.get("normalize"):
        mods["columns_normalized"] = len(report["normalize"])
    return mods


def refine_silver(name: str, engine: Engine) -> tuple[pd.DataFrame, dict, dict]:
    """Refine one source from its Bronze table; returns ``(silver_df, report, stats)``."""
    spec = _SPECS[name]
    bronze = read_bronze_table(spec.table, engine)
    kept, rejected = split_rejected(bronze)
    silver_df, report = spec.to_silver(kept)
    stats = {
        "bronze_rows": len(bronze),
        "rejected": len(rejected),
        "treated": len(kept),
        "silver_rows": len(silver_df),
        "modifications": _modifications(report),
        "reject_reasons": (
            rejected[PARSE_REASON].value_counts().to_dict() if len(rejected) else {}
        ),
    }
    logger.info(
        "Refined %s: bronze=%d rejected=%d -> silver=%d %s",
        name,
        stats["bronze_rows"],
        stats["rejected"],
        stats["silver_rows"],
        stats["modifications"],
    )
    return silver_df, report, stats


def silver_summary_markdown(stats_by_source: dict[str, dict]) -> str:
    """Per-source recap: bronze rows, rejected, ingested (silver) and modifications."""
    lines = [
        "| source | bronze rows | rejected | silver rows | modifications |",
        "|---|---|---|---|---|",
    ]
    for name, st in stats_by_source.items():
        mods = ", ".join(f"{k}={v}" for k, v in st["modifications"].items()) or "—"
        lines.append(
            f"| {name} | {st['bronze_rows']} | {st['rejected']} | {st['silver_rows']} | {mods} |"
        )
    return "\n".join(lines)
