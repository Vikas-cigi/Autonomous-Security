"""
SQLAlchemy 2.x ORM models for Enterprise Remediation Planner.
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


class RemediationPlanORM(Base):
    __tablename__ = "rp_plans"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "decision_id", name="uq_rp_plans_tenant_decision"
        ),
        Index("ix_rp_plans_tenant_finding", "tenant_id", "finding_id"),
        Index("ix_rp_plans_tenant_status", "tenant_id", "status"),
        Index("ix_rp_plans_tenant_exec", "tenant_id", "execution_type"),
        Index("ix_rp_plans_tenant_asset", "tenant_id", "asset_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    decision_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    asset_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_type: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    planned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    first_planned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_planned_at: Mapped[datetime] = mapped_column(
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

    versions: Mapped[list["RemediationPlanVersionORM"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    history_rows: Mapped[list["RemediationHistoryORM"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class RemediationPlanVersionORM(Base):
    __tablename__ = "rp_plan_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "plan_id", "version", name="uq_rp_plan_version"
        ),
        Index("ix_rp_versions_finding", "tenant_id", "finding_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    plan_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("rp_plans.id", ondelete="CASCADE"),
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

    plan: Mapped["RemediationPlanORM"] = relationship(back_populates="versions")


class RemediationHistoryORM(Base):
    __tablename__ = "rp_plan_history"
    __table_args__ = (
        Index("ix_rp_history_plan", "tenant_id", "plan_id"),
        Index("ix_rp_history_finding", "tenant_id", "finding_id"),
        Index("ix_rp_history_action", "tenant_id", "action"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    plan_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("rp_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    execution_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    plan: Mapped[Optional["RemediationPlanORM"]] = relationship(
        back_populates="history_rows"
    )


class AuditLogORM(Base):
    __tablename__ = "rp_audit_log"
    __table_args__ = (Index("ix_rp_audit_tenant_action", "tenant_id", "action"),)

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
