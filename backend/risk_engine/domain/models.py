"""Core Enterprise Risk Engine domain models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from risk_engine.domain.enums import (
    FactorCategory,
    FactorPolarity,
    RecommendedSLA,
    RiskLevel,
    RiskPriority,
)
from risk_engine.domain.weights import (
    ALGORITHM_VERSION,
    priority_for_level,
    risk_level_for_score,
    sla_for_level,
)


class RiskFactor(FortiBaseModel):
    """Explainable elevating or mitigating risk factor."""

    id: UUID = Field(default_factory=new_id)
    category: FactorCategory = Field(...)
    polarity: FactorPolarity = Field(...)
    label: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=2000)
    raw_score: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    weighted_contribution: float = Field(..., ge=-1.0, le=1.0)


class BusinessImpact(FortiBaseModel):
    """Business impact assessment for the finding."""

    score: float = Field(..., ge=0.0, le=1.0)
    asset_criticality: float = Field(default=0.0, ge=0.0, le=1.0)
    business_criticality: float = Field(default=0.0, ge=0.0, le=1.0)
    environment_score: float = Field(default=0.0, ge=0.0, le=1.0)
    customer_facing: bool = Field(default=False)
    explanation: str = Field(..., min_length=1, max_length=2000)


class TechnicalImpact(FortiBaseModel):
    """Technical impact assessment (CVSS / exploitability)."""

    score: float = Field(..., ge=0.0, le=1.0)
    cvss_normalized: float = Field(default=0.0, ge=0.0, le=1.0)
    epss_score: float = Field(default=0.0, ge=0.0, le=1.0)
    actively_exploited: bool = Field(default=False)
    in_cisa_kev: bool = Field(default=False)
    finding_age_factor: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=1, max_length=2000)


class ComplianceImpact(FortiBaseModel):
    """Compliance impact assessment."""

    score: float = Field(..., ge=0.0, le=1.0)
    frameworks: List[str] = Field(default_factory=list)
    highest_framework_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=1, max_length=2000)


class OperationalImpact(FortiBaseModel):
    """Operational / exposure impact assessment."""

    score: float = Field(..., ge=0.0, le=1.0)
    internet_facing: bool = Field(default=False)
    ioc_match_count: int = Field(default=0, ge=0)
    mitre_technique_count: int = Field(default=0, ge=0)
    exposure_score: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=1, max_length=2000)


class RiskExplanation(FortiBaseModel):
    """Human-readable explanation of the enterprise risk score."""

    summary: str = Field(..., min_length=1, max_length=8000)
    top_elevating_factors: List[str] = Field(default_factory=list)
    top_mitigating_factors: List[str] = Field(default_factory=list)
    rationale: str = Field(..., min_length=1, max_length=8000)


class EnterpriseRiskScore(FortiBaseModel):
    """Normalized overall enterprise risk score (0-100) with level mapping."""

    value: float = Field(..., ge=0.0, le=100.0)
    level: RiskLevel = Field(...)
    normalized_0_1: float = Field(..., ge=0.0, le=1.0)
    historical_blend_applied: bool = Field(default=False)

    @model_validator(mode="after")
    def sync_level(self) -> EnterpriseRiskScore:
        expected = risk_level_for_score(self.value)
        if self.level != expected:
            object.__setattr__(self, "level", expected)
        if abs(self.normalized_0_1 - (self.value / 100.0)) > 1e-6:
            object.__setattr__(self, "normalized_0_1", round(self.value / 100.0, 6))
        return self


class RiskAssessment(TimestampedModel):
    """
    Risk assessment envelope optionally attached to a SecurityFindingObject.

    Joined by finding_id + tenant_id. Does not mutate the finding.
    Executes after Trust Scoring and before Decision Service.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    enterprise_risk_score: EnterpriseRiskScore = Field(...)
    risk_level: RiskLevel = Field(...)
    priority: RiskPriority = Field(...)
    recommended_sla: RecommendedSLA = Field(...)
    factors: List[RiskFactor] = Field(default_factory=list)
    business_impact: BusinessImpact = Field(...)
    technical_impact: TechnicalImpact = Field(...)
    compliance_impact: ComplianceImpact = Field(...)
    operational_impact: OperationalImpact = Field(...)
    explanation: RiskExplanation = Field(...)
    trust_score_used: float = Field(..., ge=0.0, le=100.0)
    scored_at: datetime = Field(default_factory=utc_now)
    algorithm_version: str = Field(
        default=ALGORITHM_VERSION,
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
    def sync_derived_fields(self) -> RiskAssessment:
        if self.risk_level != self.enterprise_risk_score.level:
            object.__setattr__(self, "risk_level", self.enterprise_risk_score.level)
        expected_sla = sla_for_level(self.risk_level)
        if self.recommended_sla != expected_sla:
            object.__setattr__(self, "recommended_sla", expected_sla)
        expected_priority = priority_for_level(self.risk_level)
        if self.priority != expected_priority:
            object.__setattr__(self, "priority", expected_priority)
        if self.last_scored_at < self.first_scored_at:
            object.__setattr__(self, "last_scored_at", self.first_scored_at)
        return self
