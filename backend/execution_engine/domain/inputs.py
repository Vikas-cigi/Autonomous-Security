"""Execution Engine input snapshots — assembled by callers from upstream modules."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, new_id, utc_now
from execution_engine.domain.enums import ExecutionMode, RollbackMode


class ExecutionAuthorizationInput(FortiBaseModel):
    """Snapshot of Approval Engine ExecutionAuthorization."""

    authorized: bool = Field(...)
    authorization_id: UUID = Field(...)
    approval_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    plan_id: UUID = Field(...)
    simulation_id: UUID = Field(...)
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reason: str = Field(default="approved", max_length=2000)

    @field_validator("issued_at", "expires_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ApprovalDecisionInput(FortiBaseModel):
    approval_id: UUID = Field(...)
    state: str = Field(..., min_length=1, max_length=32)
    decided_by: Optional[str] = Field(default=None, max_length=256)
    auto: bool = Field(default=False)


class DecisionExecutionInput(FortiBaseModel):
    decision_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    decision: str = Field(..., min_length=1, max_length=64)
    recommended_action: Optional[str] = Field(default=None, max_length=128)


class PlanStepInput(FortiBaseModel):
    step_id: UUID = Field(default_factory=new_id)
    sequence: int = Field(..., ge=1)
    action: str = Field(..., min_length=1, max_length=512)
    target: str = Field(..., min_length=1, max_length=512)
    kind: str = Field(default="remediation", max_length=64)
    execution_type: str = Field(default="configuration_change", max_length=64)
    is_destructive: bool = Field(default=False)
    estimated_duration_seconds: int = Field(default=60, ge=1)
    timeout_seconds: int = Field(default=300, ge=1)
    max_retries: int = Field(default=1, ge=0, le=10)
    depends_on_sequences: List[int] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class RollbackStepInput(FortiBaseModel):
    step_id: UUID = Field(default_factory=new_id)
    sequence: int = Field(..., ge=1)
    action: str = Field(..., min_length=1, max_length=512)
    target: str = Field(..., min_length=1, max_length=512)
    estimated_duration_seconds: int = Field(default=60, ge=1)
    timeout_seconds: int = Field(default=300, ge=1)
    compensates_sequence: Optional[int] = Field(default=None, ge=1)


class RemediationPlanInput(FortiBaseModel):
    plan_id: UUID = Field(...)
    execution_type: str = Field(..., min_length=1, max_length=64)
    summary: str = Field(..., min_length=1, max_length=2000)
    steps: List[PlanStepInput] = Field(..., min_length=1)
    rollback_steps: List[RollbackStepInput] = Field(default_factory=list)
    rollback_automatic: bool = Field(default=False)
    mode: ExecutionMode = Field(default=ExecutionMode.SEQUENTIAL)


class SimulationExecutionInput(FortiBaseModel):
    simulation_id: UUID = Field(...)
    outcome: str = Field(..., min_length=1, max_length=32)
    safe_to_execute: bool = Field(...)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class RiskExecutionInput(FortiBaseModel):
    enterprise_risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: str = Field(..., min_length=1, max_length=32)


class TrustExecutionInput(FortiBaseModel):
    trust_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    trust_level: Optional[str] = Field(default=None, max_length=32)


class AssetExecutionInput(FortiBaseModel):
    asset_id: UUID = Field(...)
    hostname: Optional[str] = Field(default=None, max_length=256)
    environment: Optional[str] = Field(default=None, max_length=64)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class OrgPolicyExecutionInput(FortiBaseModel):
    """Org knobs for execution behavior (not Policy Engine evaluation)."""

    policy_version: str = Field(default="1.0.0", max_length=64)
    default_timeout_seconds: int = Field(default=300, ge=1)
    default_max_retries: int = Field(default=1, ge=0, le=10)
    auto_rollback_on_failure: bool = Field(default=True)
    allow_partial_success: bool = Field(default=False)
    require_simulation_safe: bool = Field(default=True)


class ExecutionRequest(FortiBaseModel):
    """Complete deterministic input to start an approved remediation execution."""

    authorization: ExecutionAuthorizationInput = Field(...)
    approval: ApprovalDecisionInput = Field(...)
    decision: DecisionExecutionInput = Field(...)
    plan: RemediationPlanInput = Field(...)
    simulation: SimulationExecutionInput = Field(...)
    risk: Optional[RiskExecutionInput] = None
    trust: Optional[TrustExecutionInput] = None
    asset: Optional[AssetExecutionInput] = None
    org_policy: OrgPolicyExecutionInput = Field(default_factory=OrgPolicyExecutionInput)
    rollback_mode: RollbackMode = Field(default=RollbackMode.AUTOMATIC)
    initiator: Optional[str] = Field(default=None, max_length=256)
    actor: Optional[str] = Field(default=None, max_length=256)
    evaluated_at: datetime = Field(default_factory=utc_now)
    queue_name: str = Field(default="default", max_length=64)

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value
