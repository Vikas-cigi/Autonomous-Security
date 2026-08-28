"""Search filters for Approval Engine."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from approval_engine.domain.enums import ApprovalState, ApprovalType


class ApprovalSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    plan_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    decision_id: Optional[UUID] = None
    simulation_id: Optional[UUID] = None
    states: Optional[List[ApprovalState]] = None
    approval_types: Optional[List[ApprovalType]] = None
    emergency: Optional[bool] = None
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class ApprovalPolicySearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    enabled: Optional[bool] = None
    name_contains: Optional[str] = Field(default=None, max_length=256)


class ApprovalAuditSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    approval_id: Optional[UUID] = None
    plan_id: Optional[UUID] = None
    actions: Optional[List[str]] = None
