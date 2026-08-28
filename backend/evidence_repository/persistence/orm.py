"""
SQLAlchemy 2.x ORM models — PostgreSQL-compatible.

Uses portable JSON columns (JSONB on PostgreSQL via dialect).
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
    """Declarative base for Evidence Repository tables."""


# Prefer PostgreSQL JSONB when available; fall back to generic JSON.
JSONType = JSON().with_variant(JSONB(), "postgresql")
UUIDType = Uuid(as_uuid=True).with_variant(PGUUID(as_uuid=True), "postgresql")


class FindingORM(Base):
    """Current-state finding row (latest version materialization)."""

    __tablename__ = "er_findings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_er_findings_tenant_fp"),
        Index("ix_er_findings_tenant_asset", "tenant_id", "asset_id"),
        Index("ix_er_findings_tenant_severity", "tenant_id", "severity"),
        Index("ix_er_findings_tenant_status", "tenant_id", "status"),
        Index("ix_er_findings_tenant_scanner", "tenant_id", "source_tool"),
        Index("ix_er_findings_tenant_corr", "tenant_id", "correlation_group_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    asset_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    source_tool: Mapped[str] = mapped_column(String(64), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    cvss_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_group_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
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

    evidence_rows: Mapped[list["EvidenceORM"]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
    )
    versions: Mapped[list["FindingVersionORM"]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
    )
    history_rows: Mapped[list["FindingHistoryORM"]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
    )


class EvidenceORM(Base):
    """Current-state evidence row."""

    __tablename__ = "er_evidence"
    __table_args__ = (
        Index("ix_er_evidence_tenant_finding", "tenant_id", "finding_id"),
        UniqueConstraint("tenant_id", "id", name="uq_er_evidence_tenant_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    finding_id: Mapped[Any] = mapped_column(
        UUIDType, ForeignKey("er_findings.id", ondelete="CASCADE"), nullable=False
    )
    raw_artifact_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    hash_algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
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

    finding: Mapped[FindingORM] = relationship(back_populates="evidence_rows")
    versions: Mapped[list["EvidenceVersionORM"]] = relationship(
        back_populates="evidence",
        cascade="all, delete-orphan",
    )


class FindingVersionORM(Base):
    """Immutable finding version snapshots."""

    __tablename__ = "er_finding_versions"
    __table_args__ = (
        UniqueConstraint("finding_id", "version", name="uq_er_finding_version"),
        Index("ix_er_finding_versions_tenant", "tenant_id", "finding_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    finding_id: Mapped[Any] = mapped_column(
        UUIDType, ForeignKey("er_findings.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    finding: Mapped[FindingORM] = relationship(back_populates="versions")


class EvidenceVersionORM(Base):
    """Immutable evidence version snapshots."""

    __tablename__ = "er_evidence_versions"
    __table_args__ = (
        UniqueConstraint("evidence_id", "version", name="uq_er_evidence_version"),
        Index("ix_er_evidence_versions_tenant", "tenant_id", "evidence_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    evidence_id: Mapped[Any] = mapped_column(
        UUIDType, ForeignKey("er_evidence.id", ondelete="CASCADE"), nullable=False
    )
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evidence: Mapped[EvidenceORM] = relationship(back_populates="versions")


class FindingHistoryORM(Base):
    """Append-only finding audit / lifecycle history."""

    __tablename__ = "er_finding_history"
    __table_args__ = (
        Index("ix_er_finding_history_tenant_finding", "tenant_id", "finding_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    finding_id: Mapped[Any] = mapped_column(
        UUIDType, ForeignKey("er_findings.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    from_lifecycle: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_lifecycle: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(String(4000), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    correlation_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    finding: Mapped[FindingORM] = relationship(back_populates="history_rows")


class AuditLogORM(Base):
    """Repository-wide audit log (searches, correlations, admin actions)."""

    __tablename__ = "er_audit_log"
    __table_args__ = (Index("ix_er_audit_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(String(4000), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
