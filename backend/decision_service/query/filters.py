"""Search filters for Enterprise Decision Service."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from decision_service.domain.enums import DecisionLifecycleStatus, SecurityDecisionType


class DecisionSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    finding_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    statuses: Optional[List[DecisionLifecycleStatus]] = None
    decision_types: Optional[List[SecurityDecisionType]] = None
    min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class DecisionAuditSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    decision_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    actions: Optional[List[str]] = None
