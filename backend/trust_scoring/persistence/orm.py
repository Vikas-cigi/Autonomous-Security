"""
SQLAlchemy 2.x ORM models for Trust Scoring — PostgreSQL-compatible.
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


class TrustAssessmentORM(Base):
    __tablename__ = "ts_assessments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "finding_id", name="uq_ts_assessments_tenant_finding"
        ),
        Index("ix_ts_assessments_tenant_score", "tenant_id", "score_value"),
        Index("ix_ts_assessments_tenant_level", "tenant_id", "confidence_level"),
        Index("ix_ts_assessments_tenant_asset", "tenant_id", "asset_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    asset_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    score_value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_level: Mapped[str] = mapped_column(String(32), nullable=False)
    recommendation_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
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

    versions: Mapped[list["TrustAssessmentVersionORM"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
    factors: Mapped[list["ConfidenceFactorORM"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
    history_rows: Mapped[list["TrustHistoryORM"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )


class TrustAssessmentVersionORM(Base):
    __tablename__ = "ts_assessment_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "assessment_id", "version", name="uq_ts_assessment_version"
        ),
        Index("ix_ts_versions_finding", "tenant_id", "finding_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    assessment_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("ts_assessments.id", ondelete="CASCADE"),
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

    assessment: Mapped["TrustAssessmentORM"] = relationship(back_populates="versions")


class ConfidenceFactorORM(Base):
    __tablename__ = "ts_confidence_factors"
    __table_args__ = (
        Index("ix_ts_factors_assessment", "tenant_id", "assessment_id"),
        Index("ix_ts_factors_finding", "tenant_id", "finding_id"),
        Index("ix_ts_factors_category", "tenant_id", "category"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    assessment_id: Mapped[Any] = mapped_column(
        UUIDType,
        ForeignKey("ts_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    finding_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    polarity: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    weighted_contribution: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    assessment: Mapped["TrustAssessmentORM"] = relationship(back_populates="factors")


class TrustHistoryORM(Base):
    __tablename__ = "ts_trust_history"
    __table_args__ = (
        Index("ix_ts_history_assessment", "tenant_id", "assessment_id"),
        Index("ix_ts_history_finding", "tenant_id", "finding_id"),
        Index("ix_ts_history_action", "tenant_id", "action"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    assessment_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType,
        ForeignKey("ts_assessments.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    trust_score_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    assessment: Mapped[Optional["TrustAssessmentORM"]] = relationship(
        back_populates="history_rows"
    )


class AuditLogORM(Base):
    __tablename__ = "ts_audit_log"
    __table_args__ = (Index("ix_ts_audit_tenant_action", "tenant_id", "action"),)

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
