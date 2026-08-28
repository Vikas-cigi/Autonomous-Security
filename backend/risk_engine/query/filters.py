"""Search filters for Enterprise Risk Engine."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from risk_engine.domain.enums import RecommendedSLA, RiskLevel, RiskPriority


class RiskAssessmentSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    finding_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    risk_levels: Optional[List[RiskLevel]] = None
    priorities: Optional[List[RiskPriority]] = None
    recommended_slas: Optional[List[RecommendedSLA]] = None
    min_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    max_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class RiskHistorySearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    assessment_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    actions: Optional[List[str]] = None
