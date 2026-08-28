"""Versioning and audit history for Verification Engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, new_id, utc_now
from verification_engine.domain.enums import AuditAction
from verification_engine.domain.models import VerificationResult


class VerificationHistory(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    verification_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    execution_id: UUID = Field(...)
    version: int = Field(..., ge=1)
    snapshot: VerificationResult = Field(...)
    change_summary: str = Field(..., min_length=1, max_length=2000)
    created_by: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class VerificationAuditRecord(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    verification_id: Optional[UUID] = None
    execution_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    plan_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    action: AuditAction = Field(...)
    actor: Optional[str] = Field(default=None, max_length=256)
    message: str = Field(..., min_length=1, max_length=4000)
    details: Dict[str, Any] = Field(default_factory=dict)
    status: Optional[str] = Field(default=None, max_length=32)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value
