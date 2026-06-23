"""Gold dataset experiments: build a versioned Gold table from a params profile + manifest.

Each profile is just a ``gold`` params override. The **dataset_version** is a stable hash of the
resolved params, so the same profile always yields the same id — and a different threshold /
horizon / window / split produces a new, comparable version (with its own manifest of base rates).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from src import config
from src.framework.lineage.tracker import _hash_df
from src.usecase.gold.features import build_gold_features, read_silver, resolve_gold_params


def dataset_version(resolved_params: dict) -> str:
    """Stable 10-char id derived from the resolved gold params (same params → same id)."""
    payload = json.dumps(resolved_params, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


def build_manifest(gold: pd.DataFrame, resolved_params: dict, version: str) -> dict:
    """Summarise a built Gold version: shape, hash, split sizes, label base rates, params."""
    label_cols = [c for c in gold.columns if c.startswith("label_failure_next_")]
    pos_rate, censored = {}, {}
    for c in label_cols:
        observed = int(gold[c].notna().sum())
        pos_rate[c] = round(int((gold[c] == 1).sum()) / observed, 6) if observed else None
        censored[c] = int(gold[c].isna().sum())
    ttf_obs = int((gold["label_ttf_censored"] == 0).sum()) if "label_ttf_censored" in gold else None
    return {
        "dataset_version": version,
        "rows": int(len(gold)),
        "cols": int(gold.shape[1]),
        "content_hash": _hash_df(gold),
        "split": {str(k): int(v) for k, v in gold["split_set"].value_counts().items()},
        "label_positive_rate": pos_rate,
        "label_censored": censored,
        "ttf_observed": ttf_obs,
        "params": resolved_params,
    }


def build_gold_version(
    silver: dict[str, pd.DataFrame], params: dict | None = None, output_dir: Path | None = None
) -> tuple[pd.DataFrame, dict]:
    """Build a Gold version from ``silver`` + a params override; optionally persist it.

    Writes ``<output_dir>/<version>/gold.csv`` and ``manifest.json`` when ``output_dir`` is set.
    """
    resolved = resolve_gold_params(params)
    version = dataset_version(resolved)
    gold = build_gold_features(silver, resolved)
    manifest = build_manifest(gold, resolved, version)
    if output_dir is not None:
        out = Path(output_dir) / version
        out.mkdir(parents=True, exist_ok=True)
        gold.to_csv(out / "gold.csv", index=False, encoding=config.CSV_ENCODING)
        (out / "manifest.json").write_text(
            json.dumps(manifest, indent=2, default=str), encoding="utf-8"
        )
    return gold, manifest


def load_silver(engine=None) -> dict[str, pd.DataFrame]:
    """Silver frames for a Gold build: from the DB if an engine is given, else in-memory."""
    if engine is not None:
        return read_silver(engine)
    from src.usecase.sources.registry import gold_sources

    return {role: spec.to_silver(spec.load_bronze())[0] for role, spec in gold_sources().items()}
