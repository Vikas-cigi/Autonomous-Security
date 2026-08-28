"""Approval Engine input snapshots — assembled by callers from upstream modules."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, utc_now


class DecisionApprovalInput(FortiBaseModel):
    decision_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    decision: str = Field(..., min_length=1, max_length=64)
    recommended_action: Optional[str] = Field(default=None, max_length=128)
    priority: Optional[str] = Field(default=None, max_length=16)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    reason: Optional[str] = Field(default=None, max_length=4000)


class PlanApprovalInput(FortiBaseModel):
    plan_id: UUID = Field(...)
    execution_type: str = Field(..., min_length=1, max_length=64)
    priority: Optional[str] = Field(default=None, max_length=16)
    summary: str = Field(..., min_length=1, max_length=2000)
    approval_required: bool = Field(default=True)
    change_window_required: bool = Field(default=False)
    planned_downtime_seconds: int = Field(default=0, ge=0)
    step_count: int = Field(default=1, ge=1)
    is_destructive: bool = Field(default=False)
    rollback_possible: bool = Field(default=True)


class SimulationApprovalInput(FortiBaseModel):
    simulation_id: UUID = Field(...)
    outcome: str = Field(..., min_length=1, max_length=32)
    safe_to_execute: bool = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    blast_radius: Optional[str] = Field(default=None, max_length=32)
    downtime_seconds: int = Field(default=0, ge=0)
    policy_violations: List[str] = Field(default_factory=list)
    summary: Optional[str] = Field(default=None, max_length=4000)


class RiskApprovalInput(FortiBaseModel):
    enterprise_risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: str = Field(..., min_length=1, max_length=32)
    business_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    compliance_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class TrustApprovalInput(FortiBaseModel):
    trust_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    trust_level: Optional[str] = Field(default=None, max_length=32)


class AssetApprovalInput(FortiBaseModel):
    asset_id: UUID = Field(...)
    hostname: Optional[str] = Field(default=None, max_length=256)
    environment: Optional[str] = Field(default=None, max_length=64)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)
    business_unit: Optional[str] = Field(default=None, max_length=128)
    compliance_tags: List[str] = Field(default_factory=list)
    internet_facing: bool = Field(default=False)


class OrgPolicyApprovalInput(FortiBaseModel):
    """Tenant / org policy knobs for approval gating."""

    policy_version: str = Field(default="1.0.0", min_length=1, max_length=64)
    auto_approve_enabled: bool = Field(default=False)
    auto_approve_max_risk_level: str = Field(default="low", max_length=32)
    require_simulation_safe: bool = Field(default=True)
    default_expiration_hours: int = Field(default=72, ge=1, le=720)
    escalation_hours: int = Field(default=24, ge=1, le=720)
    emergency_bypass_roles: List[str] = Field(default_factory=list)
    attributes: Dict[str, str] = Field(default_factory=dict)


class ApprovalSubmitRequest(FortiBaseModel):
    """Complete deterministic input to open an approval request."""

    decision: DecisionApprovalInput = Field(...)
    plan: PlanApprovalInput = Field(...)
    simulation: SimulationApprovalInput = Field(...)
    risk: RiskApprovalInput = Field(...)
    asset: Optional[AssetApprovalInput] = None
    trust: Optional[TrustApprovalInput] = None
    org_policy: OrgPolicyApprovalInput = Field(default_factory=OrgPolicyApprovalInput)
    policy_id: Optional[UUID] = None
    emergency: bool = Field(default=False)
    requester: Optional[str] = Field(default=None, max_length=256)
    actor: Optional[str] = Field(default=None, max_length=256)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value


class RecordDecisionRequest(FortiBaseModel):
    """Human or system decision on a pending approval stage/request."""

    approval_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    approve: bool = Field(...)
    approver: str = Field(..., min_length=1, max_length=256)
    approver_role: Optional[str] = Field(default=None, max_length=64)
    stage_id: Optional[UUID] = None
    comment: Optional[str] = Field(default=None, max_length=4000)
    actor: Optional[str] = Field(default=None, max_length=256)


class DelegateApprovalRequest(FortiBaseModel):
    approval_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    assignment_id: UUID = Field(...)
    from_approver: str = Field(..., min_length=1, max_length=256)
    to_approver: str = Field(..., min_length=1, max_length=256)
    reason: str = Field(..., min_length=1, max_length=2000)
    actor: Optional[str] = Field(default=None, max_length=256)


class EscalateApprovalRequest(FortiBaseModel):
    approval_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    reason: str = Field(..., min_length=1, max_length=2000)
    escalate_to_role: Optional[str] = Field(default=None, max_length=64)
    actor: Optional[str] = Field(default=None, max_length=256)
