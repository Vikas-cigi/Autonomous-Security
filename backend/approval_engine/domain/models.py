"""Core Enterprise Approval Engine domain models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import (
    ActorReference,
    FortiBaseModel,
    TimestampedModel,
    new_id,
    utc_now,
)
from models.enums import ApprovalStatus
from models.remediation import ApprovalRecord
from approval_engine.domain.enums import (
    ApprovalMode,
    ApprovalState,
    ApprovalType,
    ApproverRole,
    AssignmentStatus,
    NotificationKind,
    NotificationStatus,
    PolicyMatchMode,
    StageStatus,
)

ALGORITHM_VERSION = "1.0.0"


class ApprovalRule(FortiBaseModel):
    """Single policy rule that selects required approver roles."""

    id: UUID = Field(default_factory=new_id)
    name: str = Field(..., min_length=1, max_length=256)
    priority: int = Field(default=100, ge=1, le=10000)
    enabled: bool = Field(default=True)
    match_mode: PolicyMatchMode = Field(default=PolicyMatchMode.ALL)
    risk_levels: List[str] = Field(default_factory=list)
    environments: List[str] = Field(default_factory=list)
    min_asset_criticality: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    compliance_tags: List[str] = Field(default_factory=list)
    business_units: List[str] = Field(default_factory=list)
    remediation_types: List[str] = Field(default_factory=list)
    require_change_window: Optional[bool] = None
    auto_approve: bool = Field(default=False)
    emergency_only: bool = Field(default=False)
    required_roles: List[ApproverRole] = Field(default_factory=list)
    approval_types: List[ApprovalType] = Field(default_factory=list)
    mode: ApprovalMode = Field(default=ApprovalMode.SEQUENTIAL)
    explanation: str = Field(default="", max_length=2000)


class ApprovalPolicy(TimestampedModel):
    """Tenant-scoped approval policy containing ordered rules."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    name: str = Field(..., min_length=1, max_length=256)
    version: str = Field(default="1.0.0", min_length=1, max_length=64)
    enabled: bool = Field(default=True)
    description: str = Field(default="", max_length=2000)
    rules: List[ApprovalRule] = Field(default_factory=list)
    default_expiration_hours: int = Field(default=72, ge=1, le=720)
    default_escalation_hours: int = Field(default=24, ge=1, le=720)
    algorithm_version: str = Field(default=ALGORITHM_VERSION, max_length=32)


class ApprovalAssignment(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    stage_id: UUID = Field(...)
    approver: str = Field(..., min_length=1, max_length=256)
    role: ApproverRole = Field(...)
    status: AssignmentStatus = Field(default=AssignmentStatus.PENDING)
    delegated_from: Optional[str] = Field(default=None, max_length=256)
    delegated_to: Optional[str] = Field(default=None, max_length=256)
    assigned_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None

    @field_validator("assigned_at", "completed_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ApprovalComment(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    approval_id: UUID = Field(...)
    author: str = Field(..., min_length=1, max_length=256)
    body: str = Field(..., min_length=1, max_length=4000)
    stage_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ApprovalNotification(FortiBaseModel):
    """Outbound notification payload prepared (not sent) by the engine."""

    id: UUID = Field(default_factory=new_id)
    approval_id: UUID = Field(...)
    kind: NotificationKind = Field(...)
    recipient: str = Field(..., min_length=1, max_length=256)
    subject: str = Field(..., min_length=1, max_length=512)
    body: str = Field(..., min_length=1, max_length=8000)
    status: NotificationStatus = Field(default=NotificationStatus.PREPARED)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ApprovalStage(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    sequence: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=256)
    approval_type: ApprovalType = Field(...)
    required_role: ApproverRole = Field(...)
    status: StageStatus = Field(default=StageStatus.PENDING)
    mode_hint: ApprovalMode = Field(default=ApprovalMode.SEQUENTIAL)
    assignments: List[ApprovalAssignment] = Field(default_factory=list)
    decided_by: Optional[str] = Field(default=None, max_length=256)
    decided_at: Optional[datetime] = None
    comment: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("decided_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ApprovalWorkflow(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    approval_id: UUID = Field(...)
    mode: ApprovalMode = Field(default=ApprovalMode.SEQUENTIAL)
    stages: List[ApprovalStage] = Field(default_factory=list)
    current_stage_sequence: int = Field(default=1, ge=1)
    escalated: bool = Field(default=False)
    escalation_reason: Optional[str] = Field(default=None, max_length=2000)

    @property
    def all_stages_approved(self) -> bool:
        if not self.stages:
            return False
        return all(s.status == StageStatus.APPROVED for s in self.stages)

    @property
    def any_stage_rejected(self) -> bool:
        return any(s.status == StageStatus.REJECTED for s in self.stages)


class ApprovalTimeline(FortiBaseModel):
    requested_at: datetime = Field(...)
    expires_at: Optional[datetime] = None
    escalate_after: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    expected_completion: Optional[datetime] = None

    @field_validator(
        "requested_at",
        "expires_at",
        "escalate_after",
        "decided_at",
        "expected_completion",
        mode="before",
    )
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ExecutionAuthorization(FortiBaseModel):
    """Authorization token for Execution Engine (governance only)."""

    authorized: bool = Field(...)
    authorization_id: UUID = Field(default_factory=new_id)
    approval_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    plan_id: UUID = Field(...)
    simulation_id: UUID = Field(...)
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reason: str = Field(..., min_length=1, max_length=2000)

    @field_validator("issued_at", "expires_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ApprovalDecision(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    approval_id: UUID = Field(...)
    state: ApprovalState = Field(...)
    decided_by: Optional[str] = Field(default=None, max_length=256)
    decided_at: Optional[datetime] = None
    comment: Optional[str] = Field(default=None, max_length=4000)
    auto: bool = Field(default=False)
    execution_authorization: Optional[ExecutionAuthorization] = None

    @field_validator("decided_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ApprovalRequest(TimestampedModel):
    """
    Approval gate envelope governing remediation execution authorization.

    Never executes infrastructure. Never calls AI. Never mutates plans/risk.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    plan_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    decision_id: UUID = Field(...)
    simulation_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    state: ApprovalState = Field(default=ApprovalState.PENDING)
    approval_types: List[ApprovalType] = Field(default_factory=list)
    policy_id: Optional[UUID] = None
    policy_version: str = Field(default="1.0.0", max_length=64)
    matched_rule_names: List[str] = Field(default_factory=list)
    workflow: ApprovalWorkflow = Field(...)
    decision: Optional[ApprovalDecision] = None
    comments: List[ApprovalComment] = Field(default_factory=list)
    notifications: List[ApprovalNotification] = Field(default_factory=list)
    timeline: ApprovalTimeline = Field(...)
    assigned_approvers: List[str] = Field(default_factory=list)
    summary: str = Field(..., min_length=1, max_length=4000)
    explanation: str = Field(..., min_length=1, max_length=8000)
    emergency: bool = Field(default=False)
    requester: Optional[str] = Field(default=None, max_length=256)
    algorithm_version: str = Field(default=ALGORITHM_VERSION, max_length=32)
    current_version: int = Field(default=1, ge=1)
    requested_at: datetime = Field(default_factory=utc_now)
    first_requested_at: datetime = Field(default_factory=utc_now)
    last_evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "requested_at", "first_requested_at", "last_evaluated_at", mode="before"
    )
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def sync_times(self) -> ApprovalRequest:
        if self.last_evaluated_at < self.first_requested_at:
            object.__setattr__(self, "last_evaluated_at", self.first_requested_at)
        return self

    @property
    def is_terminal(self) -> bool:
        return self.state in {
            ApprovalState.APPROVED,
            ApprovalState.REJECTED,
            ApprovalState.CANCELLED,
            ApprovalState.EXPIRED,
            ApprovalState.AUTO_APPROVED,
        }

    @property
    def execution_authorized(self) -> bool:
        return self.state in {ApprovalState.APPROVED, ApprovalState.AUTO_APPROVED}

    def to_canonical_approval_record(self) -> ApprovalRecord:
        """Export to canonical ApprovalRecord for RemediationObject binding."""

        if self.state == ApprovalState.AUTO_APPROVED:
            status = ApprovalStatus.APPROVED
        elif self.state == ApprovalState.APPROVED:
            status = ApprovalStatus.APPROVED
        elif self.state == ApprovalState.REJECTED:
            status = ApprovalStatus.REJECTED
        elif self.state == ApprovalState.EXPIRED:
            status = ApprovalStatus.EXPIRED
        elif self.state == ApprovalState.CANCELLED:
            status = ApprovalStatus.REVOKED
        else:
            status = ApprovalStatus.PENDING

        approver = None
        decided_at = None
        comment = None
        if self.decision:
            decided_at = self.decision.decided_at
            comment = self.decision.comment
            if self.decision.decided_by:
                approver = ActorReference(
                    actor_id=new_id(),
                    display_name=self.decision.decided_by,
                    actor_type="user",
                )
            elif self.state == ApprovalState.AUTO_APPROVED:
                approver = ActorReference(
                    actor_id=new_id(),
                    display_name="system:auto_approve",
                    actor_type="system",
                )
                decided_at = decided_at or self.requested_at

        # Canonical model requires approver+decided_at for APPROVED/REJECTED
        if status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            if approver is None:
                approver = ActorReference(
                    actor_id=new_id(),
                    display_name="system:approval_engine",
                    actor_type="system",
                )
            if decided_at is None:
                decided_at = utc_now()

        return ApprovalRecord(
            status=status,
            requested_at=self.requested_at,
            decided_at=decided_at,
            approver=approver,
            comment=comment,
        )
