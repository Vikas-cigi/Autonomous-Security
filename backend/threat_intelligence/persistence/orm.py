"""
SQLAlchemy 2.x ORM models for Threat Intelligence — PostgreSQL-compatible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid


class Base(DeclarativeBase):
    pass


JSONType = JSON().with_variant(JSONB(), "postgresql")
UUIDType = Uuid(as_uuid=True).with_variant(PGUUID(as_uuid=True), "postgresql")


class ThreatIntelligenceORM(Base):
    __tablename__ = "ti_intelligence"
    __table_args__ = (
        Index("ix_ti_intel_tenant_finding", "tenant_id", "finding_id"),
        Index("ix_ti_intel_tenant_conf", "tenant_id", "confidence_score"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    finding_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    actively_exploited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    in_cisa_kev: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    versions: Mapped[list["ThreatIntelVersionORM"]] = relationship(
        back_populates="intel",
        cascade="all, delete-orphan",
    )
    history_rows: Mapped[list["ThreatIntelHistoryORM"]] = relationship(
        back_populates="intel",
        cascade="all, delete-orphan",
    )


class ThreatIntelVersionORM(Base):
    __tablename__ = "ti_intel_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "intel_id", "version", name="uq_ti_intel_version"
        ),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    intel_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("ti_intelligence.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    intel: Mapped["ThreatIntelligenceORM"] = relationship(back_populates="versions")


class ThreatIntelHistoryORM(Base):
    __tablename__ = "ti_intel_history"
    __table_args__ = (Index("ix_ti_history_intel", "tenant_id", "intel_id"),)

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    intel_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("ti_intelligence.id", ondelete="SET NULL"),
        nullable=True,
    )
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    intel: Mapped[Optional["ThreatIntelligenceORM"]] = relationship(
        back_populates="history_rows"
    )


class CVERecordORM(Base):
    __tablename__ = "ti_cve_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cve_id", name="uq_ti_cve_tenant"),
        Index("ix_ti_cve_id", "cve_id"),
        Index("ix_ti_cve_kev", "in_cisa_kev"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    cve_id: Mapped[str] = mapped_column(String(32), nullable=False)
    in_cisa_kev: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actively_exploited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    epss_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class IOCRecordORM(Base):
    __tablename__ = "ti_iocs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "ioc_type",
            "normalized_value",
            name="uq_ti_ioc_tenant_value",
        ),
        Index("ix_ti_ioc_norm", "normalized_value"),
        Index("ix_ti_ioc_type", "ioc_type"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    ioc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(2048), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ThreatFeedORM(Base):
    __tablename__ = "ti_feeds"
    __table_args__ = (
        Index("ix_ti_feeds_provider", "provider"),
        UniqueConstraint("tenant_id", "provider", "name", name="uq_ti_feed_tenant_prov"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditLogORM(Base):
    __tablename__ = "ti_audit_log"
    __table_args__ = (Index("ix_ti_audit_tenant", "tenant_id", "created_at"),)

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
