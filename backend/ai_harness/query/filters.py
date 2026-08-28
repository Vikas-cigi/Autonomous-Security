"""Search filters for AI Harness."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from ai_harness.domain.enums import AIExecutionStatus


class AIExecutionSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    request_id: Optional[UUID] = None
    correlation_id: Optional[UUID] = None
    statuses: Optional[List[AIExecutionStatus]] = None
    provider: Optional[str] = Field(default=None, max_length=64)
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class AIAuditSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    execution_id: Optional[UUID] = None
    request_id: Optional[UUID] = None
    actions: Optional[List[str]] = None
