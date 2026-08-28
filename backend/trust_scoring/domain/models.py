"""Core Trust Scoring domain models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from models.enums import SourceTool
from trust_scoring.domain.enums import (
    CrossValidationStatus,
    EvidenceQualityTier,
    FactorCategory,
    FactorPolarity,
    RecommendationConfidence,
    TrustLevel,
)
from trust_scoring.domain.weights import trust_level_for_score


class ConfidenceFactor(FortiBaseModel):
    """Explainable supporting or negative confidence factor."""

    id: UUID = Field(default_factory=new_id)
    category: FactorCategory = Field(...)
    polarity: FactorPolarity = Field(...)
    label: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=2000)
    raw_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized component contribution before weighting.",
    )
    weight: float = Field(..., ge=0.0, le=1.0)
    weighted_contribution: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Signed contribution toward the aggregated 0–1 score.",
    )


class EvidenceQuality(FortiBaseModel):
    """Assessed quality of attached evidence artifacts."""

    tier: EvidenceQualityTier = Field(...)
    score: float = Field(..., ge=0.0, le=1.0)
    evidence_count: int = Field(..., ge=0)
    validated_count: int = Field(default=0, ge=0)
    hashed_count: int = Field(default=0, ge=0)
    lineage_count: int = Field(default=0, ge=0)
    average_evidence_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=1, max_length=2000)


class ScannerConfidence(FortiBaseModel):
    """Multi-scanner confidence aggregate."""

    score: float = Field(..., ge=0.0, le=1.0)
    primary_tool: SourceTool = Field(...)
    observation_count: int = Field(..., ge=0)
    unique_tools: List[SourceTool] = Field(default_factory=list)
    average_scanner_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    severity_agreement_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=1, max_length=2000)


class CrossValidationResult(FortiBaseModel):
    """Cross-validation outcome across scanner observations."""

    status: CrossValidationStatus = Field(...)
    score: float = Field(..., ge=0.0, le=1.0)
    confirming_tools: List[SourceTool] = Field(default_factory=list)
    conflicting_tools: List[SourceTool] = Field(default_factory=list)
    agreement_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=1, max_length=2000)


class HistoricalReliability(FortiBaseModel):
    """Historical reliability of similar findings / scanners."""

    score: float = Field(..., ge=0.0, le=1.0)
    sample_size: int = Field(default=0, ge=0)
    true_positive_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    false_positive_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    scanner_accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=1, max_length=2000)


class FindingCorrelation(FortiBaseModel):
    """Correlation / duplicate / consistency analysis result."""

    score: float = Field(..., ge=0.0, le=1.0)
    correlated_finding_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    severity_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    type_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    asset_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    conflicting_status: bool = Field(default=False)
    explanation: str = Field(..., min_length=1, max_length=2000)


class TrustScore(FortiBaseModel):
    """Normalized overall trust score (0–100) with level mapping."""

    value: float = Field(..., ge=0.0, le=100.0)
    level: TrustLevel = Field(...)
    normalized_0_1: float = Field(..., ge=0.0, le=1.0)
    time_decay_multiplier: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def sync_level(self) -> TrustScore:
        expected = trust_level_for_score(self.value)
        if self.level != expected:
            object.__setattr__(self, "level", expected)
        if abs(self.normalized_0_1 - (self.value / 100.0)) > 1e-6:
            object.__setattr__(self, "normalized_0_1", round(self.value / 100.0, 6))
        return self


class TrustAssessment(TimestampedModel):
    """
    Trust assessment envelope optionally attached to a SecurityFindingObject.

    Joined by ``finding_id`` + ``tenant_id``. Does not mutate the finding.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    trust_score: TrustScore = Field(...)
    confidence_level: TrustLevel = Field(...)
    recommendation_confidence: RecommendationConfidence = Field(...)
    supporting_factors: List[ConfidenceFactor] = Field(default_factory=list)
    negative_factors: List[ConfidenceFactor] = Field(default_factory=list)
    evidence_quality: Optional[EvidenceQuality] = None
    scanner_confidence: Optional[ScannerConfidence] = None
    cross_validation: Optional[CrossValidationResult] = None
    historical_reliability: Optional[HistoricalReliability] = None
    finding_correlation: Optional[FindingCorrelation] = None
    asset_confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    threat_intel_confidence_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    ioc_confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence_explanation: str = Field(..., min_length=1, max_length=8000)
    scored_at: datetime = Field(default_factory=utc_now)
    algorithm_version: str = Field(
        default="1.0.0",
        min_length=1,
        max_length=32,
        description="Deterministic scoring algorithm version for reproducibility.",
    )
    current_version: int = Field(default=1, ge=1)
    first_scored_at: datetime = Field(default_factory=utc_now)
    last_scored_at: datetime = Field(default_factory=utc_now)

    @field_validator("scored_at", "first_scored_at", "last_scored_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def sync_confidence_level(self) -> TrustAssessment:
        if self.confidence_level != self.trust_score.level:
            object.__setattr__(self, "confidence_level", self.trust_score.level)
        if self.last_scored_at < self.first_scored_at:
            object.__setattr__(self, "last_scored_at", self.first_scored_at)
        return self
