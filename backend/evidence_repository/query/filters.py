"""Search / filter contracts for the Evidence Repository."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel
from models.enums import FindingStatus, FindingType, Severity, SourceTool
from evidence_repository.domain.enums import LifecycleState


class FindingSearchFilter(FortiBaseModel):
    """
    Multi-tenant aware finding search filter.

    ``tenant_id`` is mandatory to enforce isolation at the query layer.
    """

    tenant_id: UUID = Field(..., description="Required tenant isolation key.")
    asset_id: Optional[UUID] = None
    severities: List[Severity] = Field(default_factory=list)
    scanners: List[SourceTool] = Field(default_factory=list)
    statuses: List[FindingStatus] = Field(default_factory=list)
    lifecycles: List[LifecycleState] = Field(default_factory=list)
    finding_types: List[FindingType] = Field(default_factory=list)
    cve_id: Optional[str] = Field(default=None, max_length=32)
    text: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Case-insensitive match against title/description.",
    )
    correlation_group_id: Optional[UUID] = None
    fingerprint: Optional[str] = Field(default=None, max_length=128)
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    include_suppressed: bool = Field(default=False)

    @field_validator("created_after", "created_before", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime filters must be timezone-aware")
        return value

    @field_validator("cve_id")
    @classmethod
    def normalize_cve(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return value.strip().upper()
