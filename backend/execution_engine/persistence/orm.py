"""
SQLAlchemy 2.x ORM models for Enterprise Execution Engine.
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


class ExecutionResultORM(Base):
    __tablename__ = "ee_executions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "plan_id", name="uq_ee_executions_tenant_plan"
        ),
        Index("ix_ee_executions_tenant_finding", "tenant_id", "finding_id"),
        Index("ix_ee_executions_tenant_approval", "tenant_id", "approval_id"),
        Index("ix_ee_executions_tenant_status", "tenant_id", "status"),
        Index("ix_ee_executions_tenant_queue", "tenant_id", "queue_name"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    plan_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    decision_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    approval_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    authorization_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    simulation_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    asset_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
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

    versions: Mapped[list["ExecutionVersionORM"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
    )
    audit_rows: Mapped[list["ExecutionAuditORM"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
    )


class ExecutionVersionORM(Base):
    __tablename__ = "ee_execution_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "execution_id", "version", name="uq_ee_execution_version"
        ),
        Index("ix_ee_versions_plan", "tenant_id", "plan_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    execution_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("ee_executions.id", ondelete="CASCADE"),
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

    execution: Mapped["ExecutionResultORM"] = relationship(back_populates="versions")


class ExecutionAuditORM(Base):
    __tablename__ = "ee_execution_audit"
    __table_args__ = (
        Index("ix_ee_audit_execution", "tenant_id", "execution_id"),
        Index("ix_ee_audit_plan", "tenant_id", "plan_id"),
        Index("ix_ee_audit_action", "tenant_id", "action"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    execution_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("ee_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    plan_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    finding_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    approval_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    execution: Mapped[Optional["ExecutionResultORM"]] = relationship(
        back_populates="audit_rows"
    )


class AuditLogORM(Base):
    __tablename__ = "ee_audit_log"
    __table_args__ = (Index("ix_ee_audit_log_tenant_action", "tenant_id", "action"),)

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
