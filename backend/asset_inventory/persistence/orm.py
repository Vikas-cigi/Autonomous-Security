"""
SQLAlchemy 2.x ORM models for Asset Inventory — PostgreSQL-compatible.
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
    """Declarative base for Asset Inventory tables."""


JSONType = JSON().with_variant(JSONB(), "postgresql")
UUIDType = Uuid(as_uuid=True).with_variant(PGUUID(as_uuid=True), "postgresql")


class BusinessUnitORM(Base):
    __tablename__ = "ai_business_units"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_ai_bu_tenant_name"),
        Index("ix_ai_bu_tenant", "tenant_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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


class EnvironmentORM(Base):
    __tablename__ = "ai_environments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_ai_env_tenant_name"),
        Index("ix_ai_env_tenant_kind", "tenant_id", "kind"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_production: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    region_hint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
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


class AssetORM(Base):
    __tablename__ = "ai_assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uq_ai_assets_tenant_ext"),
        Index("ix_ai_assets_tenant_type", "tenant_id", "asset_type"),
        Index("ix_ai_assets_tenant_status", "tenant_id", "status"),
        Index("ix_ai_assets_tenant_bu", "tenant_id", "business_unit_id"),
        Index("ix_ai_assets_tenant_env", "tenant_id", "environment_id"),
        Index("ix_ai_assets_tenant_crit", "tenant_id", "criticality_tier"),
        Index("ix_ai_assets_tenant_provider", "tenant_id", "cloud_provider"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(253), nullable=True)
    fqdn: Mapped[Optional[str]] = mapped_column(String(253), nullable=True)
    business_unit_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    environment_id: Mapped[Optional[Any]] = mapped_column(UUIDType, nullable=True)
    criticality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    criticality_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    exposure_level: Mapped[str] = mapped_column(String(64), nullable=False)
    cloud_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    crown_jewel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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

    versions: Mapped[list["AssetVersionORM"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    history_rows: Mapped[list["AssetHistoryORM"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )


class AssetVersionORM(Base):
    __tablename__ = "ai_asset_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "asset_id", "version", name="uq_ai_asset_version"
        ),
        Index("ix_ai_asset_versions_asset", "tenant_id", "asset_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    asset_id: Mapped[Any] = mapped_column(
        UUIDType, ForeignKey("ai_assets.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    asset: Mapped["AssetORM"] = relationship(back_populates="versions")


class AssetHistoryORM(Base):
    __tablename__ = "ai_asset_history"
    __table_args__ = (
        Index("ix_ai_asset_history_asset", "tenant_id", "asset_id"),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    asset_id: Mapped[Any] = mapped_column(
        UUIDType, ForeignKey("ai_assets.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    asset: Mapped["AssetORM"] = relationship(back_populates="history_rows")


class AssetRelationshipORM(Base):
    __tablename__ = "ai_asset_relationships"
    __table_args__ = (
        Index("ix_ai_rel_tenant_source", "tenant_id", "source_asset_id"),
        Index("ix_ai_rel_tenant_target", "tenant_id", "target_asset_id"),
        UniqueConstraint(
            "tenant_id",
            "source_asset_id",
            "target_asset_id",
            "relationship_type",
            name="uq_ai_rel_edge",
        ),
    )

    id: Mapped[Any] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    tenant_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    source_asset_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    target_asset_id: Mapped[Any] = mapped_column(UUIDType, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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


class AuditLogORM(Base):
    __tablename__ = "ai_audit_log"
    __table_args__ = (Index("ix_ai_audit_tenant_created", "tenant_id", "created_at"),)

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
