"""Central project configuration: data schema, columns and paths.

Centralising these constants avoids duplication across the ingestion,
visualisation and CLI modules, and provides a single source of truth for the
schema described in ``CLAUDE.md``.
"""

from __future__ import annotations

from pathlib import Path

# ─── Project paths ───────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
DATA_RAW_DIR: Path = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR: Path = PROJECT_ROOT / "data" / "processed"
ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts" / "ingestions" / "incidents"
DEFAULT_INPUT_CSV: Path = DATA_RAW_DIR / "incidents.csv"
RUNS_REGISTRY_PATH: Path = ARTIFACTS_DIR / "runs_registry.json"

# ─── Source data schema (see CLAUDE.md) ──────────────────────────────────────
# NOTE: these names mirror the input CSV columns and must NOT be translated.
ID_COLUMN: str = "incident_id"
DATE_COLUMN: str = "date"
TIME_COLUMN: str = "time"
MACHINE_COLUMN: str = "machine_id"
SEVERITY_COLUMN: str = "severity"
SHIFT_COLUMN: str = "shift"
COMMENT_COLUMN: str = "comment"

# Columns holding personally identifiable information (PII).
PII_COLUMNS: tuple[str, ...] = ("operator_name", "operator_badge", "comment")

# Signal columns (boolean 0/1). The order drives the display order.
SIGNAL_COLUMNS: tuple[str, ...] = (
    "type_surchauffe",
    "type_baisse_pression",
    "type_vibration",
    "type_bruit_mecanique",
    "type_surconsommation",
    "type_blocage_mecanique",
    "type_alarme_capteur",
    "type_arret_urgence",
    "type_defaut_qualite",
)

# Full set of columns expected on input.
EXPECTED_COLUMNS: tuple[str, ...] = (
    ID_COLUMN,
    DATE_COLUMN,
    TIME_COLUMN,
    "operator_name",
    MACHINE_COLUMN,
    SEVERITY_COLUMN,
    "operator_badge",
    COMMENT_COLUMN,
    SHIFT_COLUMN,
    *SIGNAL_COLUMNS,
)

# Computed columns added by the pipeline.
DATETIME_COLUMN: str = "datetime"
N_SIGNALS_COLUMN: str = "n_active_signals"
CONFIDENCE_COLUMN: str = "confidence_index"

# ─── Formats ─────────────────────────────────────────────────────────────────
DATE_FORMAT: str = "%Y-%m-%d"  # ISO 8601
CSV_SEPARATOR: str = ","
CSV_ENCODING: str = "utf-8"

# ─── Anonymisation ───────────────────────────────────────────────────────────
SALT_ENV_VAR: str = "ANONYMIZATION_SALT"
PSEUDONYM_LENGTH_ENV_VAR: str = "PSEUDONYM_LENGTH"
DEFAULT_PSEUDONYM_LENGTH: int = 16
BADGE_PREFIX: str = "OP_"
BADGE_HASH_LENGTH: int = 6

# ─── Telemetry source ────────────────────────────────────────────────────────
# Second data source: machine telemetry (no PII, no anonymisation needed).
TELEMETRY_ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts" / "ingestions" / "telemetry"
DEFAULT_TELEMETRY_CSV: Path = DATA_RAW_DIR / "telemetry.csv"
TELEMETRY_RUNS_REGISTRY_PATH: Path = TELEMETRY_ARTIFACTS_DIR / "runs_registry.json"

TELEMETRY_TIMESTAMP_COLUMN: str = "timestamp"
# Numeric parameters measured per machine over time.
TELEMETRY_PARAM_COLUMNS: tuple[str, ...] = (
    "temperature_c",
    "pressure_bar",
    "voltage_mean_v",
    "rotation_mean_rpm",
    "pieces_produced",
)
TELEMETRY_EXPECTED_COLUMNS: tuple[str, ...] = (
    MACHINE_COLUMN,
    TELEMETRY_TIMESTAMP_COLUMN,
    *TELEMETRY_PARAM_COLUMNS,
)

# ─── Machines / maintenance source ───────────────────────────────────────────
# Third data source: PostgreSQL dump (machine referential + maintenance events),
# loaded into a local SQLite database via SQLAlchemy ORM.
MACHINES_ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts" / "ingestions" / "machines"
DEFAULT_MACHINES_SQL: Path = DATA_RAW_DIR / "machines.sql"
MACHINES_RUNS_REGISTRY_PATH: Path = MACHINES_ARTIFACTS_DIR / "runs_registry.json"

# Source key in the SQL is ``machine_code``; renamed to MACHINE_COLUMN on load
# for consistency with the other sources (and future cross-source joins).
MAINTENANCE_TIMESTAMP_COLUMN: str = "maintenance_at"
MAINTENANCE_TYPE_COLUMN: str = "maintenance_type"
MAINTENANCE_COMPONENT_COLUMN: str = "component"
MAINTENANCE_DURATION_COLUMN: str = "duration_hours"
MAINTENANCE_INCIDENT_COLUMN: str = "related_incident_id"
MACHINE_CRITICALITY_COLUMN: str = "criticality"
