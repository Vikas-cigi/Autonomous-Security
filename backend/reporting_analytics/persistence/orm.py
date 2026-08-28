"""
SQLAlchemy 2.x ORM models for Enterprise Reporting & Analytics Platform.
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


class ReportORM(Base):
    __tablename__ = "ra_reports"
    __table_args__ = (
        Index("ix_ra_reports_tenant_type", "tenant_id", "report_type"),
        Index("ix_ra_reports_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0.0"
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    generated_at: Mapped[Optional[datetime]] = mapped_column(
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

    versions: Mapped[list["ReportVersionORM"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class ReportVersionORM(Base):
    __tablename__ = "ra_report_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "report_id", "version", name="uq_ra_report_version"
        ),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    report_id: Mapped[Any] = mapped_column(
        UUIDType, ForeignKey("ra_reports.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report: Mapped["ReportORM"] = relationship(back_populates="versions")


class DashboardORM(Base):
    __tablename__ = "ra_dashboards"
    __table_args__ = (
        Index("ix_ra_dashboards_tenant_type", "tenant_id", "dashboard_type"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    dashboard_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
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


class AnalyticsSnapshotORM(Base):
    __tablename__ = "ra_analytics_snapshots"
    __table_args__ = (Index("ix_ra_snapshots_tenant", "tenant_id", "created_at"),)

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False, default="snapshot")
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


class KPIRecordORM(Base):
    __tablename__ = "ra_kpis"
    __table_args__ = (
        Index("ix_ra_kpis_tenant_snapshot", "tenant_id", "snapshot_id"),
        Index("ix_ra_kpis_tenant_name", "tenant_id", "name"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    snapshot_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    kpi_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    trend: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReportScheduleORM(Base):
    __tablename__ = "ra_report_schedules"
    __table_args__ = (Index("ix_ra_schedules_tenant", "tenant_id", "enabled"),)

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    cadence: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
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


class ExportResultORM(Base):
    __tablename__ = "ra_exports"
    __table_args__ = (Index("ix_ra_exports_tenant", "tenant_id", "format"),)

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    request_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
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


class ReportingAuditORM(Base):
    __tablename__ = "ra_reporting_audit"
    __table_args__ = (
        Index("ix_ra_audit_tenant_action", "tenant_id", "action"),
        Index("ix_ra_audit_report", "tenant_id", "report_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    report_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    dashboard_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    export_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    schedule_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
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


class AuditLogORM(Base):
    __tablename__ = "ra_audit_log"
    __table_args__ = (Index("ix_ra_audit_log_tenant_action", "tenant_id", "action"),)

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
