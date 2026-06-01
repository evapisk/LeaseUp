"""ORM models. Naming mirrors the property-intel spec, adapted to restaurants:
building -> establishment, plus closure (compliance) events."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, JSONColumn


class ScoutEatsDataSource(Base):
    """Registry of Socrata datasets we ingest."""

    __tablename__ = "scouteats_data_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    dataset_id: Mapped[str] = mapped_column(String(32))
    target_model: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ScoutEatsIngestionRun(Base):
    """Observability: one row per ingest invocation."""

    __tablename__ = "scouteats_ingestion_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    persisted: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ScoutEatsRawRecord(Base):
    """Full raw payload + checksum for change detection. Upsert by
    (source_key, source_record_id)."""

    __tablename__ = "scouteats_raw_record"
    __table_args__ = (
        UniqueConstraint("source_key", "source_record_id", name="uq_raw_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    source_record_id: Mapped[str] = mapped_column(String(255), index=True)
    payload: Mapped[dict] = mapped_column(JSONColumn)
    checksum: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ScoutEatsEstablishment(Base):
    """A deduplicated restaurant entity (the 'building' analog)."""

    __tablename__ = "scouteats_establishment"

    id: Mapped[int] = mapped_column(primary_key=True)
    camis: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    borough: Mapped[str | None] = mapped_column(String(32), nullable=True)
    zipcode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cuisine: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bin: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    bbl: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    community_board: Mapped[str | None] = mapped_column(String(16), nullable=True)
    council_district: Mapped[str | None] = mapped_column(String(16), nullable=True)
    nta: Mapped[str | None] = mapped_column(String(16), nullable=True)
    latest_grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    latest_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_inspection_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_closed: Mapped[bool] = mapped_column(default=False)
    last_closure_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    identifiers: Mapped[list["ScoutEatsIdentifier"]] = relationship(
        back_populates="establishment", cascade="all, delete-orphan"
    )
    violations: Mapped[list["ScoutEatsViolation"]] = relationship(
        back_populates="establishment", cascade="all, delete-orphan"
    )
    compliance_events: Mapped[list["ScoutEatsComplianceEvent"]] = relationship(
        back_populates="establishment", cascade="all, delete-orphan"
    )


class ScoutEatsIdentifier(Base):
    """Indexed identifiers (CAMIS/BIN/BBL) used for identity resolution."""

    __tablename__ = "scouteats_identifier"
    __table_args__ = (
        UniqueConstraint("id_type", "id_value", name="uq_identifier"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    establishment_id: Mapped[int] = mapped_column(
        ForeignKey("scouteats_establishment.id", ondelete="CASCADE"), index=True
    )
    id_type: Mapped[str] = mapped_column(String(32), index=True)
    id_value: Mapped[str] = mapped_column(String(64), index=True)

    establishment: Mapped[ScoutEatsEstablishment] = relationship(
        back_populates="identifiers"
    )


class ScoutEatsViolation(Base):
    """A normalized inspection violation line."""

    __tablename__ = "scouteats_violation"
    __table_args__ = (
        UniqueConstraint(
            "source_key", "source_record_id", name="uq_violation_source"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    establishment_id: Mapped[int] = mapped_column(
        ForeignKey("scouteats_establishment.id", ondelete="CASCADE"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    source_record_id: Mapped[str] = mapped_column(String(255), index=True)
    raw_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("scouteats_raw_record.id"), nullable=True
    )
    violation_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    violation_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_category: Mapped[str] = mapped_column(String(16), default="DOHMH")
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    respondent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disposition_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)

    establishment: Mapped[ScoutEatsEstablishment] = relationship(
        back_populates="violations"
    )


class ScoutEatsComplianceEvent(Base):
    """A closure / re-open event derived from the inspection ACTION column."""

    __tablename__ = "scouteats_compliance_event"
    __table_args__ = (
        UniqueConstraint(
            "source_key", "source_record_id", name="uq_compliance_source"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    establishment_id: Mapped[int] = mapped_column(
        ForeignKey("scouteats_establishment.id", ondelete="CASCADE"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    source_record_id: Mapped[str] = mapped_column(String(255), index=True)
    raw_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("scouteats_raw_record.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32))  # closed/re-closed/re-opened
    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    action_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)

    establishment: Mapped[ScoutEatsEstablishment] = relationship(
        back_populates="compliance_events"
    )
