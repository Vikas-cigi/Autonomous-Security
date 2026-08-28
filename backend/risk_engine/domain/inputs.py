"""Risk scoring input DTOs — snapshots consumed by the Enterprise Risk Engine.

Callers assemble these from Evidence Repository, Asset Inventory, Threat
Intelligence, Trust Scoring, and finding metadata. The engine never calls
external APIs, AI models, or sibling module ORM tables directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, utc_now
from risk_engine.domain.enums import BusinessContext, ComplianceFramework


class FindingRiskBaselineInput(FortiBaseModel):
    """Baseline signals taken from the SecurityFindingObject."""

    finding_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    asset_id: UUID = Field(...)
    finding_age_days: float = Field(default=0.0, ge=0.0)
    severity_hint: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Optional scanner severity mapped to 0-10 when CVSS absent.",
    )
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value


class CvssInput(FortiBaseModel):
    """CVSS v3 / v4 base score inputs."""

    version: str = Field(default="3.1", min_length=1, max_length=16)
    base_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    exploitability_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    impact_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    vector: Optional[str] = Field(default=None, max_length=256)


class ThreatIntelRiskInput(FortiBaseModel):
    """Threat intelligence signals that elevate enterprise risk."""

    enrichment_present: bool = Field(default=False)
    epss_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    in_cisa_kev: bool = Field(default=False)
    actively_exploited: bool = Field(default=False)
    mitre_technique_count: int = Field(default=0, ge=0)
    ioc_match_count: int = Field(default=0, ge=0)
    max_ioc_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    intel_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AssetRiskInput(FortiBaseModel):
    """Asset inventory + business context for risk."""

    asset_id: UUID = Field(...)
    asset_criticality: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Normalized asset criticality from inventory (0-1).",
    )
    business_criticality: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Business impact criticality of the workload (0-1).",
    )
    environments: List[BusinessContext] = Field(default_factory=list)
    internet_facing: bool = Field(default=False)
    customer_facing: bool = Field(default=False)
    compliance_tags: List[ComplianceFramework] = Field(default_factory=list)


class TrustRiskInput(FortiBaseModel):
    """Trust Scoring Engine output consumed as a risk pillar."""

    trust_score: float = Field(..., ge=0.0, le=100.0)
    trust_level: Optional[str] = Field(default=None, max_length=32)
    recommendation_confidence: Optional[str] = Field(default=None, max_length=32)


class HistoricalRiskInput(FortiBaseModel):
    """Prior enterprise risk for the same finding / similar assets."""

    prior_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    sample_size: int = Field(default=0, ge=0)
    days_since_last_assessment: Optional[float] = Field(default=None, ge=0.0)


class EvidenceRiskInput(FortiBaseModel):
    """Lightweight evidence quality signal (does not re-score trust)."""

    evidence_count: int = Field(default=0, ge=0)
    validated_evidence_count: int = Field(default=0, ge=0)
    average_evidence_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RiskScoringInput(FortiBaseModel):
    """
    Complete deterministic input bundle for enterprise risk scoring.

    Identical inputs always produce identical RiskAssessment score components.
    """

    finding: FindingRiskBaselineInput = Field(...)
    trust: TrustRiskInput = Field(...)
    cvss: Optional[CvssInput] = None
    threat_intel: Optional[ThreatIntelRiskInput] = None
    asset: Optional[AssetRiskInput] = None
    historical: Optional[HistoricalRiskInput] = None
    evidence: Optional[EvidenceRiskInput] = None
    apply_historical_blend: bool = Field(default=True)

    @field_validator("finding")
    @classmethod
    def finding_required(cls, value: FindingRiskBaselineInput) -> FindingRiskBaselineInput:
        return value
