"""SQLAlchemy ORM models for the 4 Bronze tables (schema-managed by Alembic).

Each table mirrors its raw source columns (types aligned with the loaded DataFrame, so any
*flagged* invalid row still inserts faithfully) plus the two flagging columns ``parse_ok`` /
``parse_reason``. A surrogate ``id`` primary key is used because duplicate rows are **kept**
(flagged, not dropped), so the natural keys are not unique in the table.
"""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src import config

SCHEMA = config.BRONZE_SCHEMA


class BronzeBase(DeclarativeBase):
    """Declarative base for the Bronze tables (all in the ``bronze`` schema)."""


class _Flagged:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parse_ok: Mapped[bool] = mapped_column(Boolean)
    parse_reason: Mapped[str] = mapped_column(String(256))


class BronzeIncident(BronzeBase, _Flagged):
    __tablename__ = "incidents"
    __table_args__ = {"schema": SCHEMA}

    incident_id: Mapped[str] = mapped_column(String(32))
    date: Mapped[str] = mapped_column(DateTime)
    time: Mapped[str] = mapped_column(String(16))
    operator_name: Mapped[str] = mapped_column(String(64))
    operator_badge: Mapped[str] = mapped_column(String(64))
    machine_id: Mapped[str] = mapped_column(String(16))
    severity: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    shift: Mapped[str] = mapped_column(String(16))
    type_surchauffe: Mapped[int] = mapped_column(Integer)
    type_baisse_pression: Mapped[int] = mapped_column(Integer)
    type_vibration: Mapped[int] = mapped_column(Integer)
    type_bruit_mecanique: Mapped[int] = mapped_column(Integer)
    type_surconsommation: Mapped[int] = mapped_column(Integer)
    type_blocage_mecanique: Mapped[int] = mapped_column(Integer)
    type_alarme_capteur: Mapped[int] = mapped_column(Integer)
    type_arret_urgence: Mapped[int] = mapped_column(Integer)
    type_defaut_qualite: Mapped[int] = mapped_column(Integer)


class BronzeTelemetry(BronzeBase, _Flagged):
    __tablename__ = "telemetry"
    __table_args__ = {"schema": SCHEMA}

    machine_id: Mapped[str] = mapped_column(String(16))
    timestamp: Mapped[str] = mapped_column(DateTime)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_bar: Mapped[float | None] = mapped_column(Float, nullable=True)
    voltage_mean_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    rotation_mean_rpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    pieces_produced: Mapped[int] = mapped_column(Integer)


class BronzeMachine(BronzeBase, _Flagged):
    __tablename__ = "machine"
    __table_args__ = {"schema": SCHEMA}

    machine_id: Mapped[str] = mapped_column(String(16))
    commissioning_date: Mapped[str] = mapped_column(DateTime)
    max_daily_capacity: Mapped[int] = mapped_column(Integer)
    max_hourly_capacity_pieces: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(32))
    production_line: Mapped[str] = mapped_column(String(16))
    location: Mapped[str] = mapped_column(String(16))
    criticality: Mapped[str] = mapped_column(String(8))


class BronzeMaintenance(BronzeBase, _Flagged):
    __tablename__ = "maintenance"
    __table_args__ = {"schema": SCHEMA}

    maintenance_id: Mapped[int] = mapped_column(Integer)
    machine_id: Mapped[str] = mapped_column(String(16))
    maintenance_at: Mapped[str] = mapped_column(DateTime(timezone=True))
    maintenance_type: Mapped[str] = mapped_column(String(16))
    action_type: Mapped[str] = mapped_column(String(32))
    component: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_incident_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration_hours: Mapped[float] = mapped_column(Float)


# The source→table mapping lives in the single registry (``SourceSpec.table``); these ORM
# classes define the Bronze schema only (managed by Alembic).
