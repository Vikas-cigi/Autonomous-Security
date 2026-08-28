"""Input snapshots consumed by the Enterprise Decision Service.

Callers assemble these from Evidence, Asset Inventory, Threat Intelligence,
Trust Scoring, Risk Engine, and Policy Engine. The service never reaches into
sibling ORM tables or scanner adapters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import ActorReference, FortiBaseModel, utc_now
from models.enums import ActionClass, PolicyScope, RecommendedAction


class FindingSnapshot(FortiBaseModel):
    """Minimal finding baseline for decision orchestration."""

    finding_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    asset_id: UUID = Field(...)
    title: Optional[str] = Field(default=None, max_length=512)
    severity: Optional[str] = Field(default=None, max_length=32)
    finding_type: Optional[str] = Field(default=None, max_length=128)
    cve_ids: List[str] = Field(default_factory=list)
    summary: Optional[str] = Field(default=None, max_length=4000)


class TrustSnapshot(FortiBaseModel):
    """Trust Scoring Engine output consumed as decision input."""

    trust_score: float = Field(..., ge=0.0, le=100.0)
    trust_level: Optional[str] = Field(default=None, max_length=32)
    recommendation_confidence: Optional[str] = Field(default=None, max_length=32)
    explanation: Optional[str] = Field(default=None, max_length=4000)


class RiskSnapshot(FortiBaseModel):
    """Risk Engine output consumed as decision input."""

    enterprise_risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: Optional[str] = Field(default=None, max_length=32)
    priority: Optional[str] = Field(default=None, max_length=16)
    recommended_sla: Optional[str] = Field(default=None, max_length=32)
    explanation: Optional[str] = Field(default=None, max_length=4000)
    business_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    technical_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    compliance_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    operational_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ThreatIntelSnapshot(FortiBaseModel):
    """Threat intelligence enrichment summary."""

    enrichment_present: bool = Field(default=False)
    in_cisa_kev: bool = Field(default=False)
    actively_exploited: bool = Field(default=False)
    epss_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    mitre_technique_count: int = Field(default=0, ge=0)
    ioc_match_count: int = Field(default=0, ge=0)
    summary: Optional[str] = Field(default=None, max_length=2000)


class AssetSnapshot(FortiBaseModel):
    """Asset inventory summary for decision context."""

    asset_id: UUID = Field(...)
    hostname: Optional[str] = Field(default=None, max_length=256)
    environment: Optional[str] = Field(default=None, max_length=64)
    criticality: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    internet_facing: bool = Field(default=False)
    customer_facing: bool = Field(default=False)
    compliance_tags: List[str] = Field(default_factory=list)


class EvidenceSnapshot(FortiBaseModel):
    """Supporting evidence summary (ids + confidence only)."""

    evidence_ids: List[UUID] = Field(default_factory=list)
    evidence_count: int = Field(default=0, ge=0)
    validated_count: int = Field(default=0, ge=0)
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    highlights: List[str] = Field(default_factory=list)


class PolicySnapshot(FortiBaseModel):
    """Optional pre-evaluated policy signals, or inputs for evaluation."""

    policy_version: str = Field(default="1.0.0", min_length=1, max_length=64)
    scope: PolicyScope = Field(default=PolicyScope.TENANT)
    action_class: ActionClass = Field(default=ActionClass.SUGGEST)
    related_policy_ids: List[UUID] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    # When set, skip live PolicyEngine and use this verdict.
    precomputed_verdict: Optional[str] = Field(default=None, max_length=32)
    precomputed_reason: Optional[str] = Field(default=None, max_length=2000)


class DecisionRequest(FortiBaseModel):
    """
    Complete orchestration request for the Enterprise Decision Service.

    Identical intelligence snapshots + flags yield deterministic orchestration
    steps; AI text may still vary unless a deterministic provider is injected.
    """

    finding: FindingSnapshot = Field(...)
    trust: TrustSnapshot = Field(...)
    risk: RiskSnapshot = Field(...)
    owner: ActorReference = Field(...)
    threat_intel: Optional[ThreatIntelSnapshot] = None
    asset: Optional[AssetSnapshot] = None
    evidence: Optional[EvidenceSnapshot] = None
    policy: PolicySnapshot = Field(default_factory=PolicySnapshot)
    approver: Optional[ActorReference] = None
    preferred_action: Optional[RecommendedAction] = None
    invoke_ai: bool = Field(
        default=True,
        description="When False, use deterministic advisor only (no provider call).",
    )
    provider_name: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional ProviderFactory lookup key; default provider when None.",
    )
    session_id: Optional[str] = Field(default=None, max_length=128)
    actor: Optional[str] = Field(default=None, max_length=256)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value
