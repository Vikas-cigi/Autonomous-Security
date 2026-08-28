"""Versioning and audit history for Reporting & Analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, new_id, utc_now
from reporting_analytics.domain.enums import AuditAction
from reporting_analytics.domain.models import Report


class ReportHistory(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    report_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    version: int = Field(..., ge=1)
    snapshot: Report = Field(...)
    change_summary: str = Field(..., min_length=1, max_length=2000)
    created_by: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class ReportingAuditRecord(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    tenant_id: Optional[UUID] = None
    report_id: Optional[UUID] = None
    dashboard_id: Optional[UUID] = None
    export_id: Optional[UUID] = None
    schedule_id: Optional[UUID] = None
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
