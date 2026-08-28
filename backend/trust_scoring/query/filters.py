"""Search filters for Trust Scoring."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from trust_scoring.domain.enums import RecommendationConfidence, TrustLevel


class TrustAssessmentSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    finding_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    trust_levels: Optional[List[TrustLevel]] = None
    recommendation_confidences: Optional[List[RecommendationConfidence]] = None
    min_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    max_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class ConfidenceFactorSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    assessment_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    categories: Optional[List[str]] = None
    polarity: Optional[str] = None


class TrustHistorySearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    assessment_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    actions: Optional[List[str]] = None
