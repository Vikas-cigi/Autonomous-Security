"""
SQLAlchemy 2.x ORM models for Enterprise Decision Service — PostgreSQL-compatible.
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


class DecisionORM(Base):
    __tablename__ = "ds_decisions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "finding_id", name="uq_ds_decisions_tenant_finding"
        ),
        Index("ix_ds_decisions_tenant_status", "tenant_id", "status"),
        Index("ix_ds_decisions_tenant_type", "tenant_id", "decision_type"),
        Index("ix_ds_decisions_tenant_asset", "tenant_id", "asset_id"),
        Index("ix_ds_decisions_tenant_confidence", "tenant_id", "confidence"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    asset_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    policy_verdict: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    first_decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_decided_at: Mapped[datetime] = mapped_column(
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

    versions: Mapped[list["DecisionVersionORM"]] = relationship(
        back_populates="decision",
        cascade="all, delete-orphan",
    )
    audit_rows: Mapped[list["DecisionAuditORM"]] = relationship(
        back_populates="decision",
        cascade="all, delete-orphan",
    )


class DecisionVersionORM(Base):
    __tablename__ = "ds_decision_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "decision_id", "version", name="uq_ds_decision_version"
        ),
        Index("ix_ds_versions_finding", "tenant_id", "finding_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    decision_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("ds_decisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    decision: Mapped["DecisionORM"] = relationship(back_populates="versions")


class DecisionAuditORM(Base):
    __tablename__ = "ds_decision_audit"
    __table_args__ = (
        Index("ix_ds_audit_decision", "tenant_id", "decision_id"),
        Index("ix_ds_audit_finding", "tenant_id", "finding_id"),
        Index("ix_ds_audit_action", "tenant_id", "action"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    decision_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("ds_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    decision_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    decision: Mapped[Optional["DecisionORM"]] = relationship(back_populates="audit_rows")


class AuditLogORM(Base):
    __tablename__ = "ds_audit_log"
    __table_args__ = (Index("ix_ds_audit_log_tenant_action", "tenant_id", "action"),)

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
