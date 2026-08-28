"""Search filters for Execution Engine."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from execution_engine.domain.enums import ExecutionStatus


class ExecutionSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    plan_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    decision_id: Optional[UUID] = None
    approval_id: Optional[UUID] = None
    statuses: Optional[List[ExecutionStatus]] = None
    queue_name: Optional[str] = Field(default=None, max_length=64)
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class ExecutionAuditSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    execution_id: Optional[UUID] = None
    plan_id: Optional[UUID] = None
    actions: Optional[List[str]] = None


class RollbackSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    execution_id: Optional[UUID] = None
    plan_id: Optional[UUID] = None
