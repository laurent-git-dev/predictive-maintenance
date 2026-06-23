"""Per-feature data-quality criteria → an OK / NOK status in the per-feature synthesis.

Each feature can declare a list of :class:`Check` (a label + a predicate over the
column profile produced by :func:`src.framework.common.profiling._profile_column` **and** the
raw column). The status is **OK** when every check passes, **NOK** otherwise (with the
failing criteria listed). Features without declared criteria get no status line.

Criteria are keyed by **feature name** (shared across layers, so the same feature is
held to the same rule in Bronze and Silver and the status reflects each layer's data).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from src import config

# Accepted time-of-day format: HH:MM, optionally with seconds (HH:MM:SS).
TIME_PATTERN = r"\d{2}:\d{2}(:\d{2})?"

# Numeric features treated as ordinal/discrete: their synthesis stays light (range
# only — no quartiles / mean / std / skew / IQR outliers, which are meaningless here).
ORDINAL_FEATURES: set[str] = {"severity"}

# Datetime features expected to be an hourly series per machine: their synthesis gets a
# per-machine QC table (duplicate stamps + missing hours).
HOURLY_PER_MACHINE_FEATURES: set[str] = {"timestamp"}

# Numeric features for which the outlier table is irrelevant (e.g. dimension capacities,
# one value per machine): the synthesis keeps range/mean/std/skew but drops outliers.
NO_OUTLIER_FEATURES: set[str] = {
    config.MACHINE_MAX_DAILY_COLUMN,
    config.MACHINE_MAX_HOURLY_COLUMN,
}

# Identifier features: no numeric/categorical synthesis (only dtype/count/unique/missing),
# even when stored as integers.
ID_FEATURES: set[str] = {config.ID_COLUMN, config.MAINTENANCE_ID_COLUMN}

# Categorical features shown with each value's share (%) instead of the most-frequent line.
SHARE_FEATURES: set[str] = {config.MAINTENANCE_TYPE_COLUMN, config.MAINTENANCE_ACTION_COLUMN}


@dataclass(frozen=True)
class Check:
    """A named criterion evaluated against a column profile, its series and the frame.

    The predicate gets ``(profile, series, df)``: most checks only use the profile or
    the series, but cross-column checks (e.g. comparing two columns) need the frame.
    """

    label: str
    passes: Callable[[dict, pd.Series, pd.DataFrame], bool]
    suggestion: str = ""  # processing to consider (Bronze -> Silver) when the check fails


# --- Reusable criteria primitives ------------------------------------------------


def _valid_date_format(e: dict, s: pd.Series, df: pd.DataFrame) -> bool:
    """Every non-null value is a valid date (``config.DATE_FORMAT``)."""
    non_na = s.dropna()
    if non_na.empty:
        return True
    if pd.api.types.is_datetime64_any_dtype(s):
        return True  # already parsed to valid timestamps in Bronze
    parsed = pd.to_datetime(non_na, format=config.DATE_FORMAT, errors="coerce")
    return bool(parsed.notna().all())


def _valid_time_format(e: dict, s: pd.Series, df: pd.DataFrame) -> bool:
    """Every non-null value matches the accepted time-of-day format."""
    non_na = s.dropna().astype(str)
    if non_na.empty:
        return True
    return bool(non_na.str.fullmatch(TIME_PATTERN).all())


def _same_distinct_as_operator_name(e: dict, s: pd.Series, df: pd.DataFrame) -> bool:
    """The column has as many distinct values as ``operator_name`` (1:1 pseudonymisation)."""
    return e["n_unique"] == df[config.OPERATOR_NAME_COLUMN].nunique(dropna=True)


def _unique_per_machine(e: dict, s: pd.Series, df: pd.DataFrame) -> bool:
    """No timestamp appears more than once for the same machine."""
    machine = config.MACHINE_COLUMN
    if machine not in df.columns:
        return e["n_unique"] == e["count"]  # no machine key: fall back to plain uniqueness
    return not df.duplicated(subset=[machine, s.name]).any()


def _related_incident_consistent(e: dict, s: pd.Series, df: pd.DataFrame) -> bool:
    """``related_incident_id`` empty for proactive maintenance, set otherwise (reactive)."""
    mtype = config.MAINTENANCE_TYPE_COLUMN
    if mtype not in df.columns:
        return True
    proactive = df[mtype] == "proactive"
    return bool(s[proactive].isna().all() and s[~proactive].notna().all())


def _no_missing_hours(e: dict, s: pd.Series, df: pd.DataFrame) -> bool:
    """Each machine has a measurement for every hour between its first and last stamp."""
    machine = config.MACHINE_COLUMN
    if machine not in df.columns:
        return True
    ts = pd.to_datetime(df[s.name], errors="coerce")
    grouped = pd.DataFrame({machine: df[machine].to_numpy(), "_t": ts}).dropna()
    for _, grp in grouped.groupby(machine):
        uniq = grp["_t"].drop_duplicates()
        if len(uniq) >= 2 and len(pd.date_range(uniq.min(), uniq.max(), freq="h")) > len(uniq):
            return False
    return True


def _in_criticality_domain(e: dict, s: pd.Series, df: pd.DataFrame) -> bool:
    """Every non-null value is one of the accepted criticality levels."""
    non_na = s.dropna().astype(str)
    return bool(non_na.isin(config.CRITICALITY_ORDER).all()) if not non_na.empty else True


def _strictly_positive(e: dict, s: pd.Series, df: pd.DataFrame) -> bool:
    """Every non-null numeric value is strictly positive."""
    num = pd.to_numeric(s, errors="coerce").dropna()
    return bool((num > 0).all()) if not num.empty else True


def _not_in_future(e: dict, s: pd.Series, df: pd.DataFrame) -> bool:
    """Every non-null date is today or in the past."""
    ts = pd.to_datetime(s, errors="coerce").dropna()
    return bool((ts <= pd.Timestamp.now()).all()) if not ts.empty else True


NO_MISSING = Check(
    "no empty value",
    lambda e, s, df: e["n_missing"] == 0,
    suggestion="missing -> impute (median/mean/mode) or drop the rows",
)
NO_DUPLICATES = Check(
    "no duplicate value",
    lambda e, s, df: e["n_unique"] == e["count"],
    suggestion="duplicates -> deduplicate (drop exact duplicates)",
)
VALID_DATE_FORMAT = Check(
    "valid date format",
    _valid_date_format,
    suggestion="bad format -> parse / normalise the date",
)
VALID_TIME_FORMAT = Check(
    "valid time format",
    _valid_time_format,
    suggestion="bad format -> parse / normalise the time",
)
SAME_DISTINCT_AS_OPERATOR_NAME = Check(
    "same distinct count as operator_name",
    _same_distinct_as_operator_name,
    suggestion="mismatch -> investigate badge<->name mapping (shared badges?)",
)
# Defect-phrased labels (shown only on failure, so they read as the problem found).
UNIQUE_PER_MACHINE = Check(
    "duplicate timestamp(s) for a machine",
    _unique_per_machine,
    suggestion="duplicates -> deduplicate (machine_id, timestamp) pairs",
)
NO_MISSING_HOURS = Check(
    "missing hourly timestamp(s) for a machine",
    _no_missing_hours,
    suggestion="gaps -> resample to hourly / fill or flag the missing hours",
)
IN_CRITICALITY_DOMAIN = Check(
    "criticality in {LOW, MEDIUM, HIGH}",
    _in_criticality_domain,
    suggestion="out of domain -> map to {LOW, MEDIUM, HIGH}",
)
STRICTLY_POSITIVE = Check(
    "strictly positive value",
    _strictly_positive,
    suggestion="non-positive -> clip or flag the values",
)
NOT_IN_FUTURE = Check(
    "date not in the future",
    _not_in_future,
    suggestion="future dates -> flag / correct",
)
RELATED_INCIDENT_CONSISTENT = Check(
    "related incident empty iff proactive (set iff reactive)",
    _related_incident_consistent,
    suggestion="inconsistent -> align related_incident_id with maintenance_type",
)


# --- Per-feature criteria registry -----------------------------------------------
# Add an entry here to attach an OK/NOK status to a feature's synthesis.
FEATURE_CHECKS: dict[str, list[Check]] = {
    "incident_id": [NO_MISSING, NO_DUPLICATES],
    "date": [NO_MISSING, VALID_DATE_FORMAT],
    "time": [NO_MISSING, VALID_TIME_FORMAT],
    "operator_name": [NO_MISSING],
    "operator_badge": [NO_MISSING, SAME_DISTINCT_AS_OPERATOR_NAME],
    "machine_id": [NO_MISSING],
    "timestamp": [NO_MISSING, UNIQUE_PER_MACHINE, NO_MISSING_HOURS],
    "severity": [NO_MISSING],
    "comment": [NO_MISSING],
    "shift": [NO_MISSING],
    # Machine referential (dimension) — every attribute must have no empty value.
    config.MACHINE_CRITICALITY_COLUMN: [NO_MISSING],
    config.MACHINE_MAX_DAILY_COLUMN: [NO_MISSING],
    config.MACHINE_MAX_HOURLY_COLUMN: [NO_MISSING],
    config.MACHINE_COMMISSIONING_COLUMN: [NO_MISSING],
    config.MACHINE_MODEL_COLUMN: [NO_MISSING],
    config.MACHINE_LINE_COLUMN: [NO_MISSING],
    config.MACHINE_LOCATION_COLUMN: [NO_MISSING],
    # Maintenance (facts).
    config.MAINTENANCE_ID_COLUMN: [NO_MISSING, NO_DUPLICATES],
    config.MAINTENANCE_TYPE_COLUMN: [NO_MISSING],
    config.MAINTENANCE_ACTION_COLUMN: [NO_MISSING],
    config.MAINTENANCE_TIMESTAMP_COLUMN: [NO_MISSING],
    config.MAINTENANCE_COMPONENT_COLUMN: [NO_MISSING],
    config.MAINTENANCE_DESCRIPTION_COLUMN: [NO_MISSING],
    config.MAINTENANCE_INCIDENT_COLUMN: [RELATED_INCIDENT_CONSISTENT],
    config.MAINTENANCE_DURATION_COLUMN: [NO_MISSING],
    # Every signal flag (type_*) must have no empty value.
    **{signal: [NO_MISSING] for signal in config.SIGNAL_COLUMNS},
    # Every telemetry parameter must have no missing value.
    **{param: [NO_MISSING] for param in config.TELEMETRY_PARAM_COLUMNS},
    # ── Silver-only features (created in Bronze -> Silver processing) ──────────────
    # Status proposed by analogy with the closest Bronze features.
    # Incidents: timestamp-like and calendar features (analogy: date / timestamp).
    config.DATETIME_COLUMN: [NO_MISSING, NOT_IN_FUTURE],
    "hour": [NO_MISSING],
    "weekday": [NO_MISSING],
    "month": [NO_MISSING],
    "is_weekend": [NO_MISSING],
    # Incidents: free-text / production flags (analogy: signal flags, 0/1, never empty).
    "comment_pii_flag": [NO_MISSING],
    "production_stop_flag": [NO_MISSING],
    # Incidents: corroboration features (analogy: a count / ratio that must be positive).
    config.N_SIGNALS_COLUMN: [NO_MISSING, STRICTLY_POSITIVE],
    config.CONFIDENCE_COLUMN: [NO_MISSING, STRICTLY_POSITIVE],
    # Telemetry: capacity breach flag (analogy: signal flags, 0/1, never empty).
    "over_capacity_flag": [NO_MISSING],
    # Maintenance: machine age (analogy: a duration that must be positive).
    "machine_age_years": [NO_MISSING, STRICTLY_POSITIVE],
}

# Source-scoped checks: (source_name, feature) -> extra checks, added to the global ones.
# Lets a feature be held to a stricter rule in one source only (e.g. machine_id is a
# primary key in the `machine` dimension, but a repeating foreign key elsewhere).
SOURCE_FEATURE_CHECKS: dict[tuple[str, str], list[Check]] = {
    ("machine", config.MACHINE_COLUMN): [NO_DUPLICATES],
}


def _resolve_checks(feature: str, source: str | None) -> list[Check]:
    """Global checks for a feature plus any source-scoped ones."""
    checks = list(FEATURE_CHECKS.get(feature, ()))
    if source is not None:
        checks += SOURCE_FEATURE_CHECKS.get((source, feature), [])
    return checks


def feature_status(
    feature: str,
    profile: dict,
    series: pd.Series,
    df: pd.DataFrame,
    source: str | None = None,
) -> tuple[str, list[str]] | None:
    """Return ``("OK"|"NOK", failing_labels)`` for a feature, or ``None`` if no criteria.

    Parameters
    ----------
    feature:
        Column name.
    profile:
        The column profile dict (``count``, ``n_unique``, ``n_missing``, …).
    series:
        The raw column (needed by format checks).
    df:
        The full frame (needed by cross-column checks).
    source:
        Source name, to add any source-scoped checks on top of the global ones.
    """
    checks = _resolve_checks(feature, source)
    if not checks:
        return None
    failures = [c.label for c in checks if not c.passes(profile, series, df)]
    return ("OK" if not failures else "NOK", failures)


def feature_report(
    feature: str,
    profile: dict,
    series: pd.Series,
    df: pd.DataFrame,
    source: str | None = None,
) -> tuple[str, list[tuple[str, str]]]:
    """Return ``(status, failing)`` for a synthesis table.

    ``status`` is ``"OK"`` / ``"NOK"`` / ``"none"`` (no criteria declared) and ``failing``
    is the list of ``(label, suggestion)`` for the failing checks.
    """
    checks = _resolve_checks(feature, source)
    if not checks:
        return ("none", [])
    failing = [(c.label, c.suggestion) for c in checks if not c.passes(profile, series, df)]
    return ("OK" if not failing else "NOK", failing)
