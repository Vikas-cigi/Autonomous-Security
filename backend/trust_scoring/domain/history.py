"""Versioning and audit history for Trust Scoring."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, new_id, utc_now
from trust_scoring.domain.enums import AuditAction
from trust_scoring.domain.models import TrustAssessment


class TrustAssessmentVersion(FortiBaseModel):
    """Immutable snapshot of a TrustAssessment."""

    id: UUID = Field(default_factory=new_id)
    assessment_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    version: int = Field(..., ge=1)
    snapshot: TrustAssessment = Field(...)
    change_summary: str = Field(..., min_length=1, max_length=2000)
    created_by: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class TrustAuditRecord(FortiBaseModel):
    """Append-only audit / history entry for trust assessment lifecycle."""

    id: UUID = Field(default_factory=new_id)
    assessment_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    action: AuditAction = Field(...)
    actor: Optional[str] = Field(default=None, max_length=256)
    message: str = Field(..., min_length=1, max_length=4000)
    details: Dict[str, Any] = Field(default_factory=dict)
    trust_score_value: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value
