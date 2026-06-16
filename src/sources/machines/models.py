"""SQLAlchemy ORM models for the machines / maintenance source.

These declarative models double as the **documented data schema** (a step-2
deliverable). They are SQLite-compatible, which lets us load the PostgreSQL dump
into a local database without depending on PostgreSQL-specific DDL.
"""

from __future__ import annotations

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for the machines source models."""


class Machine(Base):
    """Machine referential (one row per machine)."""

    __tablename__ = "machine"

    machine_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    commissioning_date: Mapped[str] = mapped_column(Date)
    max_daily_capacity: Mapped[int] = mapped_column(Integer)
    max_hourly_capacity_pieces: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(32))
    production_line: Mapped[str] = mapped_column(String(16))
    location: Mapped[str] = mapped_column(String(16))
    criticality: Mapped[str] = mapped_column(String(8))

    maintenances: Mapped[list[Maintenance]] = relationship(back_populates="machine")


class Maintenance(Base):
    """Maintenance event (many per machine)."""

    __tablename__ = "maintenance"

    maintenance_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_code: Mapped[str] = mapped_column(ForeignKey("machine.machine_code"))
    maintenance_at: Mapped[str] = mapped_column(DateTime)
    maintenance_type: Mapped[str] = mapped_column(String(16))  # proactive | reactive
    action_type: Mapped[str] = mapped_column(String(32))
    component: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String)
    related_incident_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duration_hours: Mapped[float] = mapped_column(Numeric(6, 2))

    machine: Mapped[Machine] = relationship(back_populates="maintenances")
