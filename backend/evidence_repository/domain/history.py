"""Finding and evidence version / history domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, new_id, utc_now
from models.enums import FindingStatus
from models.evidence import EvidenceObject
from models.security_finding import SecurityFindingObject
from evidence_repository.domain.enums import AuditAction, LifecycleState, to_lifecycle


class FindingVersion(FortiBaseModel):
    """Immutable snapshot of a finding at a specific version."""

    id: UUID = Field(default_factory=new_id)
    finding_id: UUID = Field(..., description="Logical finding identity.")
    tenant_id: UUID = Field(...)
    version: int = Field(..., ge=1, description="Monotonic version number.")
    snapshot: SecurityFindingObject = Field(
        ...,
        description="Full canonical finding snapshot at this version.",
    )
    change_summary: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Why this version was created.",
    )
    created_by: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class EvidenceVersion(FortiBaseModel):
    """Immutable snapshot of an evidence object at a specific version."""

    id: UUID = Field(default_factory=new_id)
    evidence_id: UUID = Field(..., description="Logical evidence identity.")
    finding_id: UUID = Field(..., description="Owning finding identity.")
    tenant_id: UUID = Field(...)
    version: int = Field(..., ge=1)
    snapshot: EvidenceObject = Field(...)
    change_summary: str = Field(..., min_length=1, max_length=2000)
    created_by: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class FindingHistory(FortiBaseModel):
    """Append-only audit / lifecycle history entry for a finding."""

    id: UUID = Field(default_factory=new_id)
    finding_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    action: AuditAction = Field(...)
    from_status: Optional[FindingStatus] = None
    to_status: Optional[FindingStatus] = None
    from_lifecycle: Optional[LifecycleState] = None
    to_lifecycle: Optional[LifecycleState] = None
    actor: Optional[str] = Field(default=None, max_length=256)
    message: str = Field(..., min_length=1, max_length=4000)
    details: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @classmethod
    def status_change(
        cls,
        *,
        finding_id: UUID,
        tenant_id: UUID,
        from_status: FindingStatus,
        to_status: FindingStatus,
        actor: Optional[str],
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> FindingHistory:
        """Factory for lifecycle transition history rows."""

        return cls(
            finding_id=finding_id,
            tenant_id=tenant_id,
            action=AuditAction.FINDING_STATUS_CHANGED,
            from_status=from_status,
            to_status=to_status,
            from_lifecycle=to_lifecycle(from_status),
            to_lifecycle=to_lifecycle(to_status),
            actor=actor,
            message=message,
            details=details or {},
        )
