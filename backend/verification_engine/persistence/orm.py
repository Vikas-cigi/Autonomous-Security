"""
SQLAlchemy 2.x ORM models for Enterprise Verification Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
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


class VerificationResultORM(Base):
    __tablename__ = "ve_verifications"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "execution_id", name="uq_ve_verifications_tenant_execution"
        ),
        Index("ix_ve_verifications_tenant_finding", "tenant_id", "finding_id"),
        Index("ix_ve_verifications_tenant_plan", "tenant_id", "plan_id"),
        Index("ix_ve_verifications_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    execution_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    plan_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    decision_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    asset_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0.0"
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    first_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_evaluated_at: Mapped[datetime] = mapped_column(
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

    versions: Mapped[list["VerificationVersionORM"]] = relationship(
        back_populates="verification",
        cascade="all, delete-orphan",
    )
    audit_rows: Mapped[list["VerificationAuditORM"]] = relationship(
        back_populates="verification",
        cascade="all, delete-orphan",
    )
    evidence_rows: Mapped[list["VerificationEvidenceORM"]] = relationship(
        back_populates="verification",
        cascade="all, delete-orphan",
    )


class VerificationVersionORM(Base):
    __tablename__ = "ve_verification_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "verification_id",
            "version",
            name="uq_ve_verification_version",
        ),
        Index("ix_ve_versions_execution", "tenant_id", "execution_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    verification_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("ve_verifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    execution_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    verification: Mapped["VerificationResultORM"] = relationship(
        back_populates="versions"
    )


class VerificationAuditORM(Base):
    __tablename__ = "ve_verification_audit"
    __table_args__ = (
        Index("ix_ve_audit_verification", "tenant_id", "verification_id"),
        Index("ix_ve_audit_execution", "tenant_id", "execution_id"),
        Index("ix_ve_audit_action", "tenant_id", "action"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    verification_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("ve_verifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    execution_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    finding_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    plan_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    verification: Mapped[Optional["VerificationResultORM"]] = relationship(
        back_populates="audit_rows"
    )


class VerificationEvidenceORM(Base):
    __tablename__ = "ve_verification_evidence"
    __table_args__ = (
        Index("ix_ve_evidence_verification", "tenant_id", "verification_id"),
        Index("ix_ve_evidence_phase", "tenant_id", "phase"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    verification_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("ve_verifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    evidence_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="observation")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    indicates_resolved: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    verification: Mapped["VerificationResultORM"] = relationship(
        back_populates="evidence_rows"
    )


class AuditLogORM(Base):
    __tablename__ = "ve_audit_log"
    __table_args__ = (Index("ix_ve_audit_log_tenant_action", "tenant_id", "action"),)

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
