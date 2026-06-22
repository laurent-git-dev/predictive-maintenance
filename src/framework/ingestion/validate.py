"""Row-level validation that **flags** (never modifies) Bronze data.

Adds two columns: ``parse_ok`` (bool) and ``parse_reason`` (normalized, ``;``-joined tokens
like ``missing:severity;range:duration_hours;duplicate``). Every original value is kept as-is.
"""

from __future__ import annotations

import logging

import pandas as pd
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

PARSE_OK, PARSE_REASON = "parse_ok", "parse_reason"

# Pydantic error 'type' -> normalized reason kind.
_KIND = {
    "missing": "missing",
    "string_pattern_mismatch": "format",
    "literal_error": "domain",
    "value_error": "invalid",
}


def _reason_token(err: dict) -> str:
    """Map one Pydantic error to a ``kind:field`` token."""
    field = str(err["loc"][0]) if err.get("loc") else "?"
    etype = err.get("type", "")
    if etype == "missing" or err.get("input") is None:
        kind = "missing"  # absent or NaN value for a required feature
    elif etype in _KIND:
        kind = _KIND[etype]
    elif etype.endswith(("_parsing", "_type")):
        kind = "type"
    elif etype.startswith(("greater_than", "less_than")):
        kind = "range"
    else:
        kind = "invalid"
    return f"{kind}:{field}"


def _clean(value):
    """Make a DataFrame cell JSON/pydantic-friendly (NaN -> None, Timestamp -> ISO)."""
    if isinstance(value, str):
        return value
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    item = getattr(value, "item", None)
    return item() if callable(item) else value


def validate_and_flag(
    df: pd.DataFrame, model: type[BaseModel], dup_keys: list[str]
) -> pd.DataFrame:
    """Return a copy of ``df`` with ``parse_ok`` / ``parse_reason`` added (no value changed)."""
    keys = [k for k in dup_keys if k in df.columns]
    dup_mask = (
        df.duplicated(subset=keys, keep="first") if keys else pd.Series(False, index=df.index)
    ).to_numpy()

    oks, reasons = [], []
    for pos, record in enumerate(df.to_dict("records")):
        tokens: set[str] = set()
        try:
            model.model_validate({k: _clean(v) for k, v in record.items()})
        except ValidationError as exc:
            tokens.update(_reason_token(e) for e in exc.errors())
        if dup_mask[pos]:
            tokens.add("duplicate")
        oks.append(not tokens)
        reasons.append(";".join(sorted(tokens)))

    out = df.copy()
    out[PARSE_OK] = oks
    out[PARSE_REASON] = reasons
    logger.info("Validated %s: %d/%d rows parse_ok", model.__name__, int(sum(oks)), len(out))
    return out
