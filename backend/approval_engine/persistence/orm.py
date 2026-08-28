"""
SQLAlchemy 2.x ORM models for Enterprise Approval Engine.
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


class ApprovalRequestORM(Base):
    __tablename__ = "ae_approvals"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "plan_id", name="uq_ae_approvals_tenant_plan"
        ),
        Index("ix_ae_approvals_tenant_finding", "tenant_id", "finding_id"),
        Index("ix_ae_approvals_tenant_decision", "tenant_id", "decision_id"),
        Index("ix_ae_approvals_tenant_sim", "tenant_id", "simulation_id"),
        Index("ix_ae_approvals_tenant_state", "tenant_id", "state"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    plan_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    decision_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    simulation_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    asset_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    emergency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    algorithm_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0.0"
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    first_requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
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

    versions: Mapped[list["ApprovalVersionORM"]] = relationship(
        back_populates="approval",
        cascade="all, delete-orphan",
    )
    audit_rows: Mapped[list["ApprovalAuditORM"]] = relationship(
        back_populates="approval",
        cascade="all, delete-orphan",
    )


class ApprovalVersionORM(Base):
    __tablename__ = "ae_approval_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "approval_id", "version", name="uq_ae_approval_version"
        ),
        Index("ix_ae_versions_plan", "tenant_id", "plan_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    approval_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("ae_approvals.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    plan_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    approval: Mapped["ApprovalRequestORM"] = relationship(back_populates="versions")


class ApprovalPolicyORM(Base):
    __tablename__ = "ae_policies"
    __table_args__ = (
        Index("ix_ae_policies_tenant_enabled", "tenant_id", "enabled"),
        UniqueConstraint("tenant_id", "name", name="uq_ae_policies_tenant_name"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0.0")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    algorithm_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0.0"
    )
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


class ApprovalAuditORM(Base):
    __tablename__ = "ae_approval_audit"
    __table_args__ = (
        Index("ix_ae_audit_approval", "tenant_id", "approval_id"),
        Index("ix_ae_audit_plan", "tenant_id", "plan_id"),
        Index("ix_ae_audit_action", "tenant_id", "action"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    approval_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("ae_approvals.id", ondelete="SET NULL"),
        nullable=True,
    )
    plan_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    finding_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    approval: Mapped[Optional["ApprovalRequestORM"]] = relationship(
        back_populates="audit_rows"
    )


class AuditLogORM(Base):
    __tablename__ = "ae_audit_log"
    __table_args__ = (Index("ix_ae_audit_log_tenant_action", "tenant_id", "action"),)

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
