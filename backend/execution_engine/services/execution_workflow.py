"""Build execution plan snapshots and resolve step dependency order."""

from __future__ import annotations

from typing import List, Set

from models.common import new_id

from execution_engine.domain.enums import ExecutionMode, RollbackMode, StepStatus
from execution_engine.domain.inputs import ExecutionRequest
from execution_engine.domain.models import (
    ExecutionPlan,
    ExecutionStep,
    RollbackPlan,
    RollbackStep,
)
from execution_engine.exceptions import InvalidExecutionRequestError


class ExecutionWorkflowService:
    """Create immutable execution/rollback plan snapshots from the request."""

    def build_execution_plan(self, request: ExecutionRequest) -> ExecutionPlan:
        steps: List[ExecutionStep] = []
        for s in sorted(request.plan.steps, key=lambda x: x.sequence):
            steps.append(
                ExecutionStep(
                    step_id=s.step_id,
                    sequence=s.sequence,
                    action=s.action,
                    target=s.target,
                    kind=s.kind,
                    status=StepStatus.PENDING,
                    timeout_seconds=s.timeout_seconds
                    or request.org_policy.default_timeout_seconds,
                    max_retries=s.max_retries
                    if s.max_retries is not None
                    else request.org_policy.default_max_retries,
                    depends_on_sequences=list(s.depends_on_sequences),
                    is_destructive=s.is_destructive,
                    metadata=dict(s.metadata),
                )
            )
        return ExecutionPlan(
            plan_id=request.plan.plan_id,
            execution_type=request.plan.execution_type,
            summary=request.plan.summary,
            mode=request.plan.mode,
            steps=steps,
        )

    def build_rollback_plan(self, request: ExecutionRequest) -> RollbackPlan:
        steps: List[RollbackStep] = []
        for s in request.plan.rollback_steps:
            steps.append(
                RollbackStep(
                    step_id=s.step_id or new_id(),
                    sequence=s.sequence,
                    action=s.action,
                    target=s.target,
                    compensates_sequence=s.compensates_sequence,
                    status=StepStatus.PENDING,
                    timeout_seconds=s.timeout_seconds,
                )
            )
        automatic = (
            request.plan.rollback_automatic
            or request.org_policy.auto_rollback_on_failure
            or request.rollback_mode == RollbackMode.AUTOMATIC
        )
        return RollbackPlan(
            mode=request.rollback_mode,
            steps=steps,
            automatic=automatic,
        )

    def ready_steps(
        self,
        plan: ExecutionPlan,
        completed_sequences: Set[int],
        *,
        failed_sequences: Set[int],
    ) -> List[ExecutionStep]:
        ready: List[ExecutionStep] = []
        for step in sorted(plan.steps, key=lambda s: s.sequence):
            if step.status not in {StepStatus.PENDING, StepStatus.QUEUED}:
                continue
            deps = set(step.depends_on_sequences)
            if deps & failed_sequences:
                continue
            if not deps.issubset(completed_sequences):
                continue
            ready.append(step)
        return ready

    def validate_mode(self, mode: ExecutionMode) -> None:
        if mode not in {ExecutionMode.SEQUENTIAL, ExecutionMode.PARALLEL}:
            raise InvalidExecutionRequestError(f"Unsupported execution mode: {mode}")
