"""Search filters for Remediation Planner."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from remediation_planner.domain.enums import ExecutionType, PlanStatus


class RemediationPlanSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    finding_id: Optional[UUID] = None
    decision_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    statuses: Optional[List[PlanStatus]] = None
    execution_types: Optional[List[ExecutionType]] = None
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class RemediationHistorySearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    plan_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    actions: Optional[List[str]] = None
