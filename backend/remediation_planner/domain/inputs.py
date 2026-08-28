"""Planning input snapshots — assembled by callers from upstream modules."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import ActorReference, FortiBaseModel, utc_now
from models.enums import DecisionAction, Priority, RecommendedAction
from remediation_planner.domain.enums import ExecutionType


class DecisionPlanInput(FortiBaseModel):
    """Approved DecisionObject fields required for planning."""

    decision_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    decision: DecisionAction = Field(...)
    recommended_action: RecommendedAction = Field(...)
    priority: Priority = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=1, max_length=8000)
    policy_version: str = Field(..., min_length=1, max_length=64)
    owner: ActorReference = Field(...)
    approver: Optional[ActorReference] = None
    related_policy_ids: List[UUID] = Field(default_factory=list)


class FindingPlanInput(FortiBaseModel):
    """SecurityFindingObject snapshot for plan generation."""

    finding_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    asset_id: UUID = Field(...)
    title: Optional[str] = Field(default=None, max_length=512)
    severity: Optional[str] = Field(default=None, max_length=32)
    finding_type: Optional[str] = Field(default=None, max_length=128)
    cve_ids: List[str] = Field(default_factory=list)
    package_name: Optional[str] = Field(default=None, max_length=256)
    current_version: Optional[str] = Field(default=None, max_length=128)
    fixed_version: Optional[str] = Field(default=None, max_length=128)


class RiskPlanInput(FortiBaseModel):
    """RiskAssessment snapshot influencing impact / window / approvals."""

    enterprise_risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: Optional[str] = Field(default=None, max_length=32)
    recommended_sla: Optional[str] = Field(default=None, max_length=32)
    business_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    technical_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    compliance_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    operational_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AssetPlanInput(FortiBaseModel):
    """Asset inventory snapshot for blast-radius and change windows."""

    asset_id: UUID = Field(...)
    hostname: Optional[str] = Field(default=None, max_length=256)
    environment: Optional[str] = Field(default=None, max_length=64)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)
    internet_facing: bool = Field(default=False)
    customer_facing: bool = Field(default=False)
    os_family: Optional[str] = Field(default=None, max_length=64)
    compliance_tags: List[str] = Field(default_factory=list)


class ThreatIntelPlanInput(FortiBaseModel):
    """Threat intelligence signals that elevate urgency / isolation steps."""

    in_cisa_kev: bool = Field(default=False)
    actively_exploited: bool = Field(default=False)
    epss_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    mitre_technique_count: int = Field(default=0, ge=0)


class PolicyPlanInput(FortiBaseModel):
    """Policy constraints for approvals and change windows."""

    policy_version: str = Field(default="1.0.0", min_length=1, max_length=64)
    require_approval: bool = Field(default=True)
    require_simulation: bool = Field(default=True)
    require_change_window: bool = Field(default=False)
    max_downtime_seconds: Optional[int] = Field(default=None, ge=0)
    related_policy_ids: List[UUID] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)


class RemediationPlanRequest(FortiBaseModel):
    """
    Complete deterministic input for remediation planning.

    Identical inputs always yield identical plan structure (IDs may differ
    unless plan_id / step ids are provided).
    """

    decision: DecisionPlanInput = Field(...)
    finding: FindingPlanInput = Field(...)
    risk: RiskPlanInput = Field(...)
    asset: Optional[AssetPlanInput] = None
    threat_intel: Optional[ThreatIntelPlanInput] = None
    policy: PolicyPlanInput = Field(default_factory=PolicyPlanInput)
    execution_type_override: Optional[ExecutionType] = None
    actor: Optional[str] = Field(default=None, max_length=256)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value
