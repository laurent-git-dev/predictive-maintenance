"""Anonymisation / pseudonymisation of operator data.

Rationale for the technical choice
-----------------------------------
The GDPR distinguishes *anonymisation* (irreversible) from *pseudonymisation*
(reversible with separately stored information). Here we aim for **strong
pseudonymisation**:

- ``operator_name`` → **truncated HMAC-SHA256** with a *secret salt* (pepper).
  A plain ``SHA-256(name)`` would be reversible through a dictionary attack
  (the name space is small and enumerable). HMAC with a secret key (the salt,
  stored outside the repository in ``.env``) prevents re-identification without
  the key, while staying **deterministic**: the same operator always gets the
  same pseudonym, preserving longitudinal analysis.

- ``operator_badge`` → **stable opaque** identifier ``OP_xxxxxx`` derived from
  the same HMAC. No mapping table (hash → identity) stored in the repository.

- ``comment`` → **kept but flagged** via ``comment_pii_flag``: free text may
  contain PII; a manual review remains recommended.

For anonymisation in the strict sense (irreversible), one would have to drop the
key or rely on **differential privacy** when publishing aggregates — out of
scope for this ingestion step.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

import pandas as pd

from src import config

logger = logging.getLogger(__name__)


def _hmac_hex(value: str, salt: str) -> str:
    """Compute the hexadecimal HMAC-SHA256 of ``value`` with key ``salt``."""
    return hmac.new(
        key=salt.encode("utf-8"),
        msg=str(value).encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def pseudonymize_name(value: str, salt: str, length: int) -> str:
    """Pseudonymise an operator name into a truncated HMAC-SHA256.

    Parameters
    ----------
    value : str
        Plaintext value (operator name).
    salt : str
        Secret salt (pepper) used as the HMAC key.
    length : int
        Length of the output hexadecimal pseudonym.
    """
    return _hmac_hex(value, salt)[:length]


def opaque_badge(value: str, salt: str) -> str:
    """Generate a stable, opaque badge identifier, ``OP_xxxxxx``."""
    digest = _hmac_hex(value, salt)[: config.BADGE_HASH_LENGTH].upper()
    return f"{config.BADGE_PREFIX}{digest}"


def pseudonymise_operators(
    df: pd.DataFrame, salt: str, pseudonym_length: int = config.DEFAULT_PSEUDONYM_LENGTH
) -> pd.DataFrame:
    """Pseudonymise the operator PII columns in place (Bronze privacy gate).

    Handles ``operator_name`` (truncated HMAC-SHA256) and ``operator_badge`` (opaque
    ``OP_xxxxxx``). Deterministic and irreversible without the secret salt. The free
    ``comment`` column is left untouched here (flagged later, in Silver).

    Raises
    ------
    ValueError
        If the salt is empty/unconfigured (weak anonymisation is forbidden).
    """
    if not salt or salt == "change-me-with-a-long-random-secret":
        raise ValueError(
            "Anonymisation salt missing or not configured. "
            f"Set {config.SALT_ENV_VAR} in .env (see .env.example)."
        )

    df = df.copy()
    if "operator_name" in df.columns:
        df["operator_name"] = df["operator_name"].map(
            lambda v: pseudonymize_name(v, salt, pseudonym_length) if pd.notna(v) else v
        )
    if "operator_badge" in df.columns:
        df["operator_badge"] = df["operator_badge"].map(
            lambda v: opaque_badge(v, salt) if pd.notna(v) else v
        )
    logger.info("Operators pseudonymised (operator_name, operator_badge).")
    return df
