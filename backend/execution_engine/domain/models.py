"""Core Enterprise Execution Engine domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from models.enums import ExecutionStatus as CanonicalExecutionStatus
from execution_engine.domain.enums import (
    ExecutionEventType,
    ExecutionMode,
    ExecutionStatus,
    RollbackMode,
    RollbackStatus,
    StepStatus,
)

ALGORITHM_VERSION = "1.0.0"


class ExecutionContext(FortiBaseModel):
    tenant_id: UUID = Field(...)
    plan_id: UUID = Field(...)
    approval_id: UUID = Field(...)
    authorization_id: UUID = Field(...)
    decision_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    simulation_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    queue_name: str = Field(default="default", max_length=64)
    initiator: Optional[str] = Field(default=None, max_length=256)
    environment: Optional[str] = Field(default=None, max_length=64)
    attributes: Dict[str, str] = Field(default_factory=dict)


class ExecutionStep(FortiBaseModel):
    step_id: UUID = Field(...)
    sequence: int = Field(..., ge=1)
    action: str = Field(..., min_length=1, max_length=512)
    target: str = Field(..., min_length=1, max_length=512)
    kind: str = Field(default="remediation", max_length=64)
    status: StepStatus = Field(default=StepStatus.PENDING)
    timeout_seconds: int = Field(default=300, ge=1)
    max_retries: int = Field(default=1, ge=0)
    attempt: int = Field(default=0, ge=0)
    depends_on_sequences: List[int] = Field(default_factory=list)
    is_destructive: bool = Field(default=False)
    metadata: Dict[str, str] = Field(default_factory=dict)


class StepExecutionResult(FortiBaseModel):
    step_id: UUID = Field(...)
    sequence: int = Field(..., ge=1)
    status: StepStatus = Field(...)
    attempt: int = Field(default=1, ge=1)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: int = Field(default=0, ge=0)
    message: str = Field(default="", max_length=4000)
    error_code: Optional[str] = Field(default=None, max_length=64)
    output: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ExecutionPlan(FortiBaseModel):
    """Immutable snapshot of the plan steps used for this execution (not mutated)."""

    plan_id: UUID = Field(...)
    execution_type: str = Field(..., max_length=64)
    summary: str = Field(..., max_length=2000)
    mode: ExecutionMode = Field(default=ExecutionMode.SEQUENTIAL)
    steps: List[ExecutionStep] = Field(..., min_length=1)


class RollbackStep(FortiBaseModel):
    step_id: UUID = Field(...)
    sequence: int = Field(..., ge=1)
    action: str = Field(..., min_length=1, max_length=512)
    target: str = Field(..., min_length=1, max_length=512)
    compensates_sequence: Optional[int] = None
    status: StepStatus = Field(default=StepStatus.PENDING)
    timeout_seconds: int = Field(default=300, ge=1)


class RollbackPlan(FortiBaseModel):
    mode: RollbackMode = Field(default=RollbackMode.AUTOMATIC)
    steps: List[RollbackStep] = Field(default_factory=list)
    automatic: bool = Field(default=False)


class RollbackExecution(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    execution_id: UUID = Field(...)
    status: RollbackStatus = Field(default=RollbackStatus.NOT_STARTED)
    mode: RollbackMode = Field(default=RollbackMode.AUTOMATIC)
    steps: List[RollbackStep] = Field(default_factory=list)
    step_results: List[StepExecutionResult] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reason: str = Field(default="", max_length=2000)

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class RollbackResult(FortiBaseModel):
    status: RollbackStatus = Field(...)
    rolled_back_sequences: List[int] = Field(default_factory=list)
    failed_sequences: List[int] = Field(default_factory=list)
    explanation: str = Field(..., min_length=1, max_length=4000)


class ExecutionEvent(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    execution_id: UUID = Field(...)
    event_type: ExecutionEventType = Field(...)
    message: str = Field(..., min_length=1, max_length=2000)
    step_id: Optional[UUID] = None
    sequence: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ExecutionLog(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    execution_id: UUID = Field(...)
    level: str = Field(default="info", max_length=16)
    message: str = Field(..., min_length=1, max_length=4000)
    step_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ExecutionTimeline(FortiBaseModel):
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    resumed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    rollback_started_at: Optional[datetime] = None
    rollback_completed_at: Optional[datetime] = None

    @field_validator(
        "queued_at",
        "started_at",
        "paused_at",
        "resumed_at",
        "completed_at",
        "cancelled_at",
        "rollback_started_at",
        "rollback_completed_at",
        mode="before",
    )
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ExecutionMetrics(FortiBaseModel):
    total_steps: int = Field(default=0, ge=0)
    succeeded_steps: int = Field(default=0, ge=0)
    failed_steps: int = Field(default=0, ge=0)
    skipped_steps: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    rollback_duration_ms: int = Field(default=0, ge=0)
    resource_metadata: Dict[str, str] = Field(default_factory=dict)


class ExecutionSummary(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    details: str = Field(..., min_length=1, max_length=8000)
    success: bool = Field(...)


class VerificationRequest(FortiBaseModel):
    """Handoff payload for Verification Engine (not executed here)."""

    execution_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    plan_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    decision_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    execution_status: ExecutionStatus = Field(...)
    succeeded_step_ids: List[UUID] = Field(default_factory=list)
    requested_at: datetime = Field(default_factory=utc_now)

    @field_validator("requested_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ExecutionResult(TimestampedModel):
    """
    Execution envelope for an approved RemediationPlan.

    Orchestrates steps only — never evaluates policy, recalculates risk/trust,
    invokes AI, or modifies the remediation plan.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    plan_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    decision_id: UUID = Field(...)
    approval_id: UUID = Field(...)
    authorization_id: UUID = Field(...)
    simulation_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING)
    context: ExecutionContext = Field(...)
    plan: ExecutionPlan = Field(...)
    step_results: List[StepExecutionResult] = Field(default_factory=list)
    rollback_plan: RollbackPlan = Field(default_factory=lambda: RollbackPlan())
    rollback_execution: Optional[RollbackExecution] = None
    rollback_result: Optional[RollbackResult] = None
    timeline: ExecutionTimeline = Field(default_factory=ExecutionTimeline)
    events: List[ExecutionEvent] = Field(default_factory=list)
    logs: List[ExecutionLog] = Field(default_factory=list)
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
    summary: Optional[ExecutionSummary] = None
    verification_request: Optional[VerificationRequest] = None
    algorithm_version: str = Field(default=ALGORITHM_VERSION, max_length=32)
    current_version: int = Field(default=1, ge=1)
    cancel_requested: bool = Field(default=False)
    pause_requested: bool = Field(default=False)
    first_started_at: Optional[datetime] = None
    last_evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("first_started_at", "last_evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT,
            ExecutionStatus.ROLLED_BACK,
            ExecutionStatus.PARTIALLY_COMPLETED,
        }

    def to_canonical_execution_status(self) -> CanonicalExecutionStatus:
        mapping = {
            ExecutionStatus.PENDING: CanonicalExecutionStatus.PENDING,
            ExecutionStatus.RUNNING: CanonicalExecutionStatus.RUNNING,
            ExecutionStatus.PAUSED: CanonicalExecutionStatus.QUEUED,
            ExecutionStatus.WAITING: CanonicalExecutionStatus.QUEUED,
            ExecutionStatus.COMPLETED: CanonicalExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED: CanonicalExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED: CanonicalExecutionStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT: CanonicalExecutionStatus.TIMED_OUT,
            ExecutionStatus.ROLLING_BACK: CanonicalExecutionStatus.FAILED,
            ExecutionStatus.ROLLED_BACK: CanonicalExecutionStatus.ROLLED_BACK,
            ExecutionStatus.PARTIALLY_COMPLETED: CanonicalExecutionStatus.FAILED,
        }
        return mapping.get(self.status, CanonicalExecutionStatus.PENDING)
