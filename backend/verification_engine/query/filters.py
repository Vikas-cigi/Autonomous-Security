"""Search filters for Verification Engine."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from verification_engine.domain.enums import VerificationStatus


class VerificationSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    execution_id: Optional[UUID] = None
    plan_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    decision_id: Optional[UUID] = None
    statuses: Optional[List[VerificationStatus]] = None
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class VerificationAuditSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    verification_id: Optional[UUID] = None
    execution_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    actions: Optional[List[str]] = None


class VerificationEvidenceSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    verification_id: Optional[UUID] = None
    phase: Optional[str] = Field(default=None, max_length=32)
