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
OPERATOR_NAME_COLUMN: str = "operator_name"
OPERATOR_BADGE_COLUMN: str = "operator_badge"
MACHINE_COLUMN: str = "machine_id"
SEVERITY_COLUMN: str = "severity"
SHIFT_COLUMN: str = "shift"
COMMENT_COLUMN: str = "comment"

# Free-text markers embedded in ``comment`` that denote a production stop.
PRODUCTION_STOP_MARKERS: tuple[str, ...] = ("arrêt ligne", "coupure urgence", "arrêt d'urgence")

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
    OPERATOR_NAME_COLUMN,
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
TELEMETRY_PIECES_COLUMN: str = "pieces_produced"
# Numeric parameters measured per machine over time.
TELEMETRY_PARAM_COLUMNS: tuple[str, ...] = (
    "temperature_c",
    "pressure_bar",
    "voltage_mean_v",
    "rotation_mean_rpm",
    TELEMETRY_PIECES_COLUMN,
)
TELEMETRY_EXPECTED_COLUMNS: tuple[str, ...] = (
    MACHINE_COLUMN,
    TELEMETRY_TIMESTAMP_COLUMN,
    *TELEMETRY_PARAM_COLUMNS,
)

# ─── Machines / maintenance source ───────────────────────────────────────────
# Third data source: PostgreSQL dump (machine referential + maintenance events),
# loaded into a local SQLite database via SQLAlchemy ORM.
MACHINES_ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts" / "ingestions" / "machines_maintenance"
DEFAULT_MACHINES_SQL: Path = DATA_RAW_DIR / "machines.sql"
MACHINES_RUNS_REGISTRY_PATH: Path = MACHINES_ARTIFACTS_DIR / "runs_registry.json"

# Source key in the SQL is ``machine_code``; renamed to MACHINE_COLUMN on load
# for consistency with the other sources (and future cross-source joins).
MAINTENANCE_ID_COLUMN: str = "maintenance_id"
MAINTENANCE_TIMESTAMP_COLUMN: str = "maintenance_at"
MAINTENANCE_TYPE_COLUMN: str = "maintenance_type"
MAINTENANCE_ACTION_COLUMN: str = "action_type"
MAINTENANCE_COMPONENT_COLUMN: str = "component"
MAINTENANCE_DESCRIPTION_COLUMN: str = "description"
MAINTENANCE_DURATION_COLUMN: str = "duration_hours"
MAINTENANCE_INCIDENT_COLUMN: str = "related_incident_id"

# Machine referential (dimension) columns and helpers.
MACHINE_TABLE: str = "machine"
MACHINE_CRITICALITY_COLUMN: str = "criticality"
MACHINE_MODEL_COLUMN: str = "model"
MACHINE_LINE_COLUMN: str = "production_line"
MACHINE_LOCATION_COLUMN: str = "location"
MACHINE_COMMISSIONING_COLUMN: str = "commissioning_date"
MACHINE_MAX_DAILY_COLUMN: str = "max_daily_capacity"
MACHINE_MAX_HOURLY_COLUMN: str = "max_hourly_capacity_pieces"
# Ordinal encoding for criticality (also defines the valid domain).
CRITICALITY_ORDER: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
# Machine attributes denormalised onto maintenance events in Silver.
MACHINE_ENRICH_COLUMNS: tuple[str, ...] = (
    MACHINE_CRITICALITY_COLUMN,
    MACHINE_LINE_COLUMN,
    MACHINE_LOCATION_COLUMN,
    MACHINE_MODEL_COLUMN,
    MACHINE_MAX_DAILY_COLUMN,
    MACHINE_MAX_HOURLY_COLUMN,
)

# ─── Cross-source analyses ───────────────────────────────────────────────────
# Analyses that combine several sources (joined on machine_id / incident_id).
ANALYSES_ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts" / "analyses"
CROSS_SOURCE_ARTIFACTS_DIR: Path = ANALYSES_ARTIFACTS_DIR / "cross_source"
CROSS_SOURCE_RUNS_REGISTRY_PATH: Path = CROSS_SOURCE_ARTIFACTS_DIR / "runs_registry.json"

# ─── Database (PostgreSQL, Dockerised) ───────────────────────────────────────
# Read from environment (.env); defaults match docker-compose.yml.
DB_ENV_DEFAULTS: dict[str, str] = {
    "POSTGRES_USER": "predictive",
    "POSTGRES_PASSWORD": "predictive",
    "POSTGRES_DB": "predictive_maintenance",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
}
DB_CONNECT_TIMEOUT_SECONDS: int = 3

# Medallion layers → PostgreSQL schemas (1 table per source in each layer).
BRONZE_SCHEMA: str = "bronze"
SILVER_SCHEMA: str = "silver"

# Display labels for the two sources sharing machines.sql (avoid machine/machines confusion).
SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "machine": "machines/machine",
    "machines": "machines/maintenance",
}


def source_artifacts_dirname(source: str) -> str:
    """Filesystem-safe artifacts/registry folder name for a source.

    Reuses ``SOURCE_DISPLAY_NAMES`` so the two ``machines.sql`` sources land in
    ``machines_machine`` / ``machines_maintenance`` (and not the ambiguous
    ``machine`` / ``machines``); other sources keep their own name.
    """
    return SOURCE_DISPLAY_NAMES.get(source, source).replace("/", "_")
