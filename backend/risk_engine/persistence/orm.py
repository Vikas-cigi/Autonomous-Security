"""
SQLAlchemy 2.x ORM models for Enterprise Risk Engine — PostgreSQL-compatible.
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


class RiskAssessmentORM(Base):
    __tablename__ = "re_assessments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "finding_id", name="uq_re_assessments_tenant_finding"
        ),
        Index("ix_re_assessments_tenant_score", "tenant_id", "score_value"),
        Index("ix_re_assessments_tenant_level", "tenant_id", "risk_level"),
        Index("ix_re_assessments_tenant_asset", "tenant_id", "asset_id"),
        Index("ix_re_assessments_tenant_priority", "tenant_id", "priority"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    asset_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    score_value: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    recommended_sla: Mapped[str] = mapped_column(String(32), nullable=False)
    trust_score_used: Mapped[float] = mapped_column(Float, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    first_scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_scored_at: Mapped[datetime] = mapped_column(
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

    versions: Mapped[list["RiskAssessmentVersionORM"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
    history_rows: Mapped[list["RiskHistoryORM"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )


class RiskAssessmentVersionORM(Base):
    __tablename__ = "re_assessment_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "assessment_id", "version", name="uq_re_assessment_version"
        ),
        Index("ix_re_versions_finding", "tenant_id", "finding_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    assessment_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("re_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    risk_score_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    assessment: Mapped["RiskAssessmentORM"] = relationship(back_populates="versions")


class RiskHistoryORM(Base):
    __tablename__ = "re_risk_history"
    __table_args__ = (
        Index("ix_re_history_assessment", "tenant_id", "assessment_id"),
        Index("ix_re_history_finding", "tenant_id", "finding_id"),
        Index("ix_re_history_action", "tenant_id", "action"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    assessment_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("re_assessments.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    risk_score_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    assessment: Mapped[Optional["RiskAssessmentORM"]] = relationship(
        back_populates="history_rows"
    )


class AuditLogORM(Base):
    __tablename__ = "re_audit_log"
    __table_args__ = (Index("ix_re_audit_tenant_action", "tenant_id", "action"),)

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
