"""Verification Engine input snapshots — assembled by callers from upstream modules."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, new_id, utc_now


class ExecutionVerificationInput(FortiBaseModel):
    """Snapshot of ExecutionResult / VerificationRequest handoff."""

    execution_id: UUID = Field(...)
    execution_status: str = Field(..., min_length=1, max_length=32)
    success: bool = Field(...)
    succeeded_step_count: int = Field(default=0, ge=0)
    failed_step_count: int = Field(default=0, ge=0)
    rolled_back: bool = Field(default=False)
    summary: Optional[str] = Field(default=None, max_length=4000)
    succeeded_step_ids: List[UUID] = Field(default_factory=list)


class PlanVerificationInput(FortiBaseModel):
    plan_id: UUID = Field(...)
    execution_type: str = Field(..., min_length=1, max_length=64)
    summary: str = Field(..., min_length=1, max_length=2000)
    expected_outcomes: List[str] = Field(default_factory=list)
    step_count: int = Field(default=1, ge=1)


class DecisionVerificationInput(FortiBaseModel):
    decision_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    decision: str = Field(..., min_length=1, max_length=64)
    recommended_action: Optional[str] = Field(default=None, max_length=128)


class FindingVerificationInput(FortiBaseModel):
    finding_id: UUID = Field(...)
    title: str = Field(..., min_length=1, max_length=512)
    severity: Optional[str] = Field(default=None, max_length=32)
    finding_type: Optional[str] = Field(default=None, max_length=64)
    status: str = Field(default="open", max_length=32)
    cve_ids: List[str] = Field(default_factory=list)
    asset_id: Optional[UUID] = None


class EvidenceItemInput(FortiBaseModel):
    evidence_id: UUID = Field(default_factory=new_id)
    kind: str = Field(default="observation", max_length=64)
    summary: str = Field(..., min_length=1, max_length=2000)
    source: Optional[str] = Field(default=None, max_length=128)
    collected_at: Optional[datetime] = None
    indicates_resolved: Optional[bool] = None
    attributes: Dict[str, str] = Field(default_factory=dict)

    @field_validator("collected_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class AssetVerificationInput(FortiBaseModel):
    asset_id: UUID = Field(...)
    hostname: Optional[str] = Field(default=None, max_length=256)
    environment: Optional[str] = Field(default=None, max_length=64)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)
    compliance_tags: List[str] = Field(default_factory=list)
    service_expected_up: bool = Field(default=True)


class RiskSnapshotInput(FortiBaseModel):
    """Pre/post risk scores provided by caller — engine does not recalculate."""

    pre_risk_score: float = Field(..., ge=0.0, le=100.0)
    post_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    risk_level: Optional[str] = Field(default=None, max_length=32)


class OrgPolicyVerificationInput(FortiBaseModel):
    policy_version: str = Field(default="1.0.0", max_length=64)
    require_rescan: bool = Field(default=True)
    require_compliance_check: bool = Field(default=False)
    require_service_check: bool = Field(default=True)
    min_risk_reduction_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    auto_close_on_verify: bool = Field(default=True)
    escalate_on_rollback: bool = Field(default=True)


class RescanResultInput(FortiBaseModel):
    """Caller-provided rescan outcome (engine does not invoke scanners)."""

    performed: bool = Field(default=False)
    finding_still_present: Optional[bool] = None
    scanner: Optional[str] = Field(default=None, max_length=64)
    summary: Optional[str] = Field(default=None, max_length=2000)
    evidence_ids: List[UUID] = Field(default_factory=list)


class VerificationRequest(FortiBaseModel):
    """Complete deterministic input for post-execution verification."""

    execution: ExecutionVerificationInput = Field(...)
    plan: PlanVerificationInput = Field(...)
    decision: DecisionVerificationInput = Field(...)
    finding: FindingVerificationInput = Field(...)
    pre_evidence: List[EvidenceItemInput] = Field(default_factory=list)
    post_evidence: List[EvidenceItemInput] = Field(default_factory=list)
    asset: Optional[AssetVerificationInput] = None
    risk: Optional[RiskSnapshotInput] = None
    org_policy: OrgPolicyVerificationInput = Field(
        default_factory=OrgPolicyVerificationInput
    )
    rescan: RescanResultInput = Field(default_factory=RescanResultInput)
    operator: Optional[str] = Field(default=None, max_length=256)
    actor: Optional[str] = Field(default=None, max_length=256)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value
