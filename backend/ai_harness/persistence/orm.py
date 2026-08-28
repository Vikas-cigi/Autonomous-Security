"""
SQLAlchemy 2.x ORM models for Enterprise AI Harness.
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


class AIExecutionORM(Base):
    __tablename__ = "ah_executions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "request_id", name="uq_ah_executions_tenant_request"
        ),
        Index("ix_ah_executions_tenant_status", "tenant_id", "status"),
        Index("ix_ah_executions_tenant_provider", "tenant_id", "selected_provider"),
        Index("ix_ah_executions_tenant_correlation", "tenant_id", "correlation_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    request_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    correlation_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    primary_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    selected_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    audit_rows: Mapped[list["AIAuditORM"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
    )


class AIAuditORM(Base):
    __tablename__ = "ah_audit"
    __table_args__ = (
        Index("ix_ah_audit_execution", "tenant_id", "execution_id"),
        Index("ix_ah_audit_request", "tenant_id", "request_id"),
        Index("ix_ah_audit_action", "tenant_id", "action"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    execution_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("ah_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    execution: Mapped[Optional["AIExecutionORM"]] = relationship(
        back_populates="audit_rows"
    )


class AuditLogORM(Base):
    __tablename__ = "ah_audit_log"
    __table_args__ = (Index("ix_ah_audit_log_tenant_action", "tenant_id", "action"),)

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
