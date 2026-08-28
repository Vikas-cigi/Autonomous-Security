"""Versioning and audit history models for assets."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, new_id, utc_now
from asset_inventory.domain.enums import AssetStatus, AuditAction
from asset_inventory.domain.models import Asset


class AssetVersion(FortiBaseModel):
    """Immutable snapshot of an asset at a specific version."""

    id: UUID = Field(default_factory=new_id)
    asset_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    version: int = Field(..., ge=1)
    snapshot: Asset = Field(...)
    change_summary: str = Field(..., min_length=1, max_length=2000)
    created_by: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class AssetHistory(FortiBaseModel):
    """Append-only history entry for asset lifecycle and mutations."""

    id: UUID = Field(default_factory=new_id)
    asset_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    action: AuditAction = Field(...)
    from_status: Optional[AssetStatus] = None
    to_status: Optional[AssetStatus] = None
    actor: Optional[str] = Field(default=None, max_length=256)
    message: str = Field(..., min_length=1, max_length=4000)
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value
