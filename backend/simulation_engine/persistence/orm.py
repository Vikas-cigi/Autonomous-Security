"""
SQLAlchemy 2.x ORM models for Enterprise Simulation Engine.
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


class SimulationResultORM(Base):
    __tablename__ = "se_simulations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "plan_id", name="uq_se_simulations_tenant_plan"
        ),
        Index("ix_se_simulations_tenant_finding", "tenant_id", "finding_id"),
        Index("ix_se_simulations_tenant_decision", "tenant_id", "decision_id"),
        Index("ix_se_simulations_tenant_outcome", "tenant_id", "outcome"),
        Index("ix_se_simulations_tenant_safe", "tenant_id", "safe_to_execute"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    plan_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    decision_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    asset_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_to_execute: Mapped[bool] = mapped_column(Boolean, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0.0"
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    simulated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    first_simulated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_simulated_at: Mapped[datetime] = mapped_column(
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

    versions: Mapped[list["SimulationVersionORM"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
    )
    audit_rows: Mapped[list["SimulationAuditORM"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
    )


class SimulationVersionORM(Base):
    __tablename__ = "se_simulation_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "simulation_id", "version", name="uq_se_simulation_version"
        ),
        Index("ix_se_versions_plan", "tenant_id", "plan_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    simulation_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("se_simulations.id", ondelete="CASCADE"),
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

    simulation: Mapped["SimulationResultORM"] = relationship(back_populates="versions")


class SimulationAuditORM(Base):
    __tablename__ = "se_simulation_audit"
    __table_args__ = (
        Index("ix_se_audit_simulation", "tenant_id", "simulation_id"),
        Index("ix_se_audit_plan", "tenant_id", "plan_id"),
        Index("ix_se_audit_action", "tenant_id", "action"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    simulation_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("se_simulations.id", ondelete="SET NULL"),
        nullable=True,
    )
    plan_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    finding_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    simulation: Mapped[Optional["SimulationResultORM"]] = relationship(
        back_populates="audit_rows"
    )


class AuditLogORM(Base):
    __tablename__ = "se_audit_log"
    __table_args__ = (Index("ix_se_audit_log_tenant_action", "tenant_id", "action"),)

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
