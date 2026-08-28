"""Core Enterprise Remediation Planner domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import ActorReference, FortiBaseModel, TimestampedModel, new_id, utc_now
from models.enums import ApprovalStatus, DecisionAction, Priority, RecommendedAction
from models.remediation import (
    RemediationPlan as CanonicalRemediationPlan,
    RemediationStep as CanonicalRemediationStep,
    RollbackPlan as CanonicalRollbackPlan,
)
from remediation_planner.domain.enums import (
    CostBand,
    DependencyType,
    ExecutionType,
    ImpactBlastRadius,
    PlanStatus,
    StepKind,
)


class Prerequisite(FortiBaseModel):
    """Condition that must be true before a step may run."""

    id: UUID = Field(default_factory=new_id)
    description: str = Field(..., min_length=1, max_length=1000)
    required: bool = Field(default=True)
    check_type: str = Field(
        default="manual",
        max_length=64,
        description="backup_verified | change_window_open | approval_granted | custom",
    )


class ValidationCheck(FortiBaseModel):
    """Post-step or post-plan validation checkpoint."""

    id: UUID = Field(default_factory=new_id)
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=2000)
    after_step_sequence: Optional[int] = Field(default=None, ge=1)
    success_criteria: str = Field(..., min_length=1, max_length=2000)
    is_blocking: bool = Field(default=True)


class RemediationStep(FortiBaseModel):
    """Ordered remediation / mitigation / validation step (planner-native)."""

    id: UUID = Field(default_factory=new_id)
    sequence: int = Field(..., ge=1)
    kind: StepKind = Field(default=StepKind.REMEDIATION)
    execution_type: ExecutionType = Field(...)
    action: str = Field(..., min_length=1, max_length=512)
    target: str = Field(..., min_length=1, max_length=512)
    description: str = Field(..., min_length=1, max_length=2000)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    estimated_duration_seconds: int = Field(default=60, ge=1, le=86400)
    is_destructive: bool = Field(default=False)
    requires_approval: bool = Field(default=False)
    prerequisites: List[Prerequisite] = Field(default_factory=list)
    parameters: Dict[str, str] = Field(default_factory=dict)

    @field_validator("parameters")
    @classmethod
    def limit_parameters(cls, value: Dict[str, str]) -> Dict[str, str]:
        if len(value) > 64:
            raise ValueError("step parameters limited to 64 keys")
        return value

    def to_canonical(self) -> CanonicalRemediationStep:
        return CanonicalRemediationStep(
            step_id=self.id,
            sequence=self.sequence,
            action=self.action,
            target=self.target,
            timeout_seconds=self.timeout_seconds,
            is_destructive=self.is_destructive,
            parameters=dict(self.parameters),
        )


class ExecutionTask(FortiBaseModel):
    """Executable task unit derived from one or more steps (still not executed)."""

    id: UUID = Field(default_factory=new_id)
    name: str = Field(..., min_length=1, max_length=256)
    execution_type: ExecutionType = Field(...)
    step_ids: List[UUID] = Field(..., min_length=1)
    sequence: int = Field(..., ge=1)
    estimated_duration_seconds: int = Field(..., ge=1)
    is_destructive: bool = Field(default=False)
    description: str = Field(..., min_length=1, max_length=2000)


class DependencyEdge(FortiBaseModel):
    """Directed dependency between steps."""

    from_step_id: UUID = Field(...)
    to_step_id: UUID = Field(...)
    dependency_type: DependencyType = Field(default=DependencyType.REQUIRES)
    rationale: str = Field(..., min_length=1, max_length=1000)


class DependencyGraph(FortiBaseModel):
    """Acyclic dependency graph over remediation steps."""

    edges: List[DependencyEdge] = Field(default_factory=list)
    topological_order: List[UUID] = Field(default_factory=list)

    def assert_acyclic(self) -> None:
        """Raise if topological_order is inconsistent with edges."""

        index = {sid: i for i, sid in enumerate(self.topological_order)}
        for edge in self.edges:
            if edge.dependency_type != DependencyType.REQUIRES:
                continue
            if edge.from_step_id not in index or edge.to_step_id not in index:
                raise ValueError("dependency references unknown step")
            if index[edge.from_step_id] >= index[edge.to_step_id]:
                raise ValueError("dependency graph is not a valid topological order")


class EstimatedImpact(FortiBaseModel):
    """Estimated operational impact of executing the plan."""

    blast_radius: ImpactBlastRadius = Field(...)
    affected_asset_count: int = Field(..., ge=0)
    downtime_seconds: int = Field(default=0, ge=0)
    risk_reduction_estimate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Expected reduction in enterprise risk (0-1).",
    )
    residual_operational_risk: float = Field(..., ge=0.0, le=1.0)
    notes: str = Field(..., min_length=1, max_length=4000)


class EstimatedDuration(FortiBaseModel):
    """Wall-clock duration estimate for the full plan."""

    execution_seconds: int = Field(..., ge=1)
    validation_seconds: int = Field(default=0, ge=0)
    buffer_seconds: int = Field(default=0, ge=0)
    total_seconds: int = Field(..., ge=1)
    human_summary: str = Field(..., min_length=1, max_length=512)


class RemediationCost(FortiBaseModel):
    """Relative cost estimate (not a billing invoice)."""

    band: CostBand = Field(...)
    relative_score: float = Field(..., ge=0.0, le=1.0)
    labor_hours: float = Field(..., ge=0.0)
    infrastructure_units: float = Field(default=0.0, ge=0.0)
    explanation: str = Field(..., min_length=1, max_length=2000)


class ApprovalRequirement(FortiBaseModel):
    """Who must approve before simulation / execution."""

    required: bool = Field(...)
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    minimum_approvers: int = Field(default=1, ge=0, le=5)
    dual_control: bool = Field(default=False)
    roles: List[str] = Field(default_factory=list)
    reason: str = Field(..., min_length=1, max_length=2000)
    designated_approver: Optional[ActorReference] = None


class ChangeWindow(FortiBaseModel):
    """Recommended maintenance / change window."""

    required: bool = Field(default=False)
    preferred_start: Optional[datetime] = None
    preferred_end: Optional[datetime] = None
    timezone_name: str = Field(default="UTC", max_length=64)
    rationale: str = Field(..., min_length=1, max_length=2000)

    @field_validator("preferred_start", "preferred_end", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def window_order(self) -> ChangeWindow:
        if (
            self.preferred_start is not None
            and self.preferred_end is not None
            and self.preferred_end <= self.preferred_start
        ):
            raise ValueError("preferred_end must be after preferred_start")
        return self


class RollbackPlan(FortiBaseModel):
    """Compensating rollback strategy (planner-native)."""

    id: UUID = Field(default_factory=new_id)
    summary: str = Field(..., min_length=1, max_length=2000)
    steps: List[RemediationStep] = Field(..., min_length=1)
    automatic: bool = Field(default=False)
    trigger_conditions: List[str] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def ordered(cls, value: List[RemediationStep]) -> List[RemediationStep]:
        sequences = [s.sequence for s in value]
        if sorted(sequences) != list(range(1, len(sequences) + 1)):
            raise ValueError("rollback step sequences must be contiguous from 1")
        return sorted(value, key=lambda s: s.sequence)

    def to_canonical(self) -> CanonicalRollbackPlan:
        return CanonicalRollbackPlan(
            plan_id=self.id,
            summary=self.summary,
            steps=[s.to_canonical() for s in self.steps],
            automatic=self.automatic,
        )


class RemediationPlan(TimestampedModel):
    """
    Enterprise remediation plan envelope.

    Converts an approved DecisionObject into a structured, executable plan
    that can later be simulated, approved, executed, and verified.
    Does not execute infrastructure changes.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    decision_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    status: PlanStatus = Field(default=PlanStatus.READY_FOR_SIMULATION)
    execution_type: ExecutionType = Field(...)
    decision_action: DecisionAction = Field(...)
    recommended_action: RecommendedAction = Field(...)
    priority: Priority = Field(...)
    summary: str = Field(..., min_length=1, max_length=2000)
    explanation: str = Field(..., min_length=1, max_length=8000)
    change_summary: str = Field(..., min_length=1, max_length=4000)
    steps: List[RemediationStep] = Field(..., min_length=1)
    execution_tasks: List[ExecutionTask] = Field(default_factory=list)
    validation_checks: List[ValidationCheck] = Field(default_factory=list)
    dependency_graph: DependencyGraph = Field(default_factory=DependencyGraph)
    rollback_plan: RollbackPlan = Field(...)
    estimated_impact: EstimatedImpact = Field(...)
    estimated_duration: EstimatedDuration = Field(...)
    cost_estimate: RemediationCost = Field(...)
    approval_requirement: ApprovalRequirement = Field(...)
    change_window: ChangeWindow = Field(...)
    policy_version: str = Field(..., min_length=1, max_length=64)
    related_policy_ids: List[UUID] = Field(default_factory=list)
    algorithm_version: str = Field(default="1.0.0", min_length=1, max_length=32)
    current_version: int = Field(default=1, ge=1)
    planned_at: datetime = Field(default_factory=utc_now)
    first_planned_at: datetime = Field(default_factory=utc_now)
    last_planned_at: datetime = Field(default_factory=utc_now)

    @field_validator("planned_at", "first_planned_at", "last_planned_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @field_validator("steps")
    @classmethod
    def ordered_steps(cls, value: List[RemediationStep]) -> List[RemediationStep]:
        sequences = [s.sequence for s in value]
        if sorted(sequences) != list(range(1, len(sequences) + 1)):
            raise ValueError("plan step sequences must be contiguous from 1")
        return sorted(value, key=lambda s: s.sequence)

    @model_validator(mode="after")
    def sync_times(self) -> RemediationPlan:
        if self.last_planned_at < self.first_planned_at:
            object.__setattr__(self, "last_planned_at", self.first_planned_at)
        return self

    def to_canonical_plan(self) -> CanonicalRemediationPlan:
        forward = [
            s
            for s in self.steps
            if s.kind in {StepKind.REMEDIATION, StepKind.MITIGATION, StepKind.PREREQUISITE}
        ]
        if not forward:
            forward = list(self.steps)
        # Re-sequence for canonical contiguous requirement
        canonical_steps = []
        for idx, step in enumerate(sorted(forward, key=lambda s: s.sequence), start=1):
            c = step.to_canonical()
            canonical_steps.append(
                CanonicalRemediationStep(
                    step_id=c.step_id,
                    sequence=idx,
                    action=c.action,
                    target=c.target,
                    timeout_seconds=c.timeout_seconds,
                    is_destructive=c.is_destructive,
                    parameters=c.parameters,
                )
            )
        return CanonicalRemediationPlan(
            plan_id=self.id,
            summary=self.summary,
            steps=canonical_steps,
            estimated_duration_seconds=self.estimated_duration.total_seconds,
        )

    def to_canonical_rollback(self) -> CanonicalRollbackPlan:
        return self.rollback_plan.to_canonical()
