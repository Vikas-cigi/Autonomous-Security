"""Versioning and audit history for threat intelligence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, new_id, utc_now
from threat_intelligence.domain.enums import AuditAction
from threat_intelligence.domain.models import ThreatIntelligence


class ThreatIntelVersion(FortiBaseModel):
    """Immutable snapshot of a ThreatIntelligence enrichment record."""

    id: UUID = Field(default_factory=new_id)
    intel_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    version: int = Field(..., ge=1)
    snapshot: ThreatIntelligence = Field(...)
    change_summary: str = Field(..., min_length=1, max_length=2000)
    created_by: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class ThreatIntelHistory(FortiBaseModel):
    """Append-only history entry for enrichment lifecycle."""

    id: UUID = Field(default_factory=new_id)
    intel_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    action: AuditAction = Field(...)
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
