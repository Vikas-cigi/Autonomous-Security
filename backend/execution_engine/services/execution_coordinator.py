"""Coordinate step execution order, pause/cancel checks, and terminal status."""

from __future__ import annotations

from typing import Optional, Set

from models.common import utc_now

from execution_engine.domain.enums import (
    ExecutionEventType,
    ExecutionMode,
    ExecutionStatus,
    RollbackMode,
    StepStatus,
)
from execution_engine.domain.models import (
    ExecutionResult,
    ExecutionSummary,
    VerificationRequest,
)
from execution_engine.services.execution_monitoring import ExecutionMonitoringService
from execution_engine.services.execution_step_executor import ExecutionStepExecutor
from execution_engine.services.execution_workflow import ExecutionWorkflowService
from execution_engine.services.rollback_service import RollbackService


class ExecutionCoordinator:
    """
    Drive the execution state machine for one ExecutionResult.

    Respects pause/cancel flags between steps. Never mutates the source plan.
    """

    def __init__(
        self,
        *,
        workflow: Optional[ExecutionWorkflowService] = None,
        step_executor: Optional[ExecutionStepExecutor] = None,
        rollback: Optional[RollbackService] = None,
        monitoring: Optional[ExecutionMonitoringService] = None,
        allow_partial_success: bool = False,
    ) -> None:
        self._workflow = workflow or ExecutionWorkflowService()
        self._steps = step_executor or ExecutionStepExecutor()
        self._rollback = rollback or RollbackService()
        self._monitor = monitoring or ExecutionMonitoringService()
        self._allow_partial = allow_partial_success

    def run(self, result: ExecutionResult) -> ExecutionResult:
        now = utc_now()
        result.status = ExecutionStatus.RUNNING
        result.timeline.started_at = now
        if result.first_started_at is None:
            result.first_started_at = now
        self._monitor.emit(result, ExecutionEventType.STARTED, "Execution started")

        completed: Set[int] = set()
        failed: Set[int] = set()
        timed_out = False

        # Seed completed from already-succeeded (resume support)
        for step in result.plan.steps:
            if step.status == StepStatus.SUCCEEDED:
                completed.add(step.sequence)
            elif step.status == StepStatus.FAILED:
                failed.add(step.sequence)

        while True:
            if result.cancel_requested:
                return self._cancel(result)
            if result.pause_requested:
                return self._pause(result)

            ready = self._workflow.ready_steps(
                result.plan, completed, failed_sequences=failed
            )
            # Also include pending with no deps not yet in completed/failed
            if not ready:
                pending = [
                    s
                    for s in result.plan.steps
                    if s.status in {StepStatus.PENDING, StepStatus.QUEUED}
                ]
                if not pending:
                    break
                # Blocked by failed deps → skip remaining
                for s in pending:
                    s.status = StepStatus.SKIPPED
                    self._monitor.log(
                        result,
                        f"Skipping step {s.sequence} due to unmet/failed dependencies",
                        level="warning",
                        step_id=s.step_id,
                    )
                break

            if result.plan.mode == ExecutionMode.SEQUENTIAL:
                batch = ready[:1]
            else:
                batch = ready

            for step in batch:
                if result.cancel_requested:
                    return self._cancel(result)
                if result.pause_requested:
                    return self._pause(result)

                step.status = StepStatus.QUEUED
                step_result = self._steps.execute(result, step)
                result.step_results = list(result.step_results) + [step_result]
                self._monitor.recompute_metrics(result)

                if step_result.status == StepStatus.SUCCEEDED:
                    completed.add(step.sequence)
                elif step_result.status == StepStatus.TIMED_OUT:
                    failed.add(step.sequence)
                    timed_out = True
                    return self._fail_or_rollback(result, timed_out=True)
                else:
                    failed.add(step.sequence)
                    if not self._allow_partial:
                        return self._fail_or_rollback(result, timed_out=False)

        return self._finalize(result, timed_out=timed_out)

    def _pause(self, result: ExecutionResult) -> ExecutionResult:
        result.status = ExecutionStatus.PAUSED
        result.timeline.paused_at = utc_now()
        result.pause_requested = False
        self._monitor.emit(result, ExecutionEventType.PAUSED, "Execution paused")
        self._monitor.recompute_metrics(result)
        result.summary = ExecutionSummary(
            headline="Execution paused",
            details=f"Paused after {result.metrics.succeeded_steps} successful steps.",
            success=False,
        )
        return result

    def _cancel(self, result: ExecutionResult) -> ExecutionResult:
        result.status = ExecutionStatus.CANCELLED
        result.timeline.cancelled_at = utc_now()
        result.timeline.completed_at = result.timeline.cancelled_at
        result.cancel_requested = False
        for step in result.plan.steps:
            if step.status in {StepStatus.PENDING, StepStatus.QUEUED, StepStatus.RUNNING}:
                step.status = StepStatus.CANCELLED
        self._monitor.emit(result, ExecutionEventType.CANCELLED, "Execution cancelled")
        self._monitor.recompute_metrics(result)
        result.summary = ExecutionSummary(
            headline="Execution cancelled",
            details="Cancellation requested by operator.",
            success=False,
        )
        return result

    def _fail_or_rollback(
        self, result: ExecutionResult, *, timed_out: bool
    ) -> ExecutionResult:
        if (
            result.rollback_plan.automatic
            and result.rollback_plan.steps
            and result.rollback_plan.mode
            in {RollbackMode.AUTOMATIC, RollbackMode.PARTIAL}
        ):
            result.status = ExecutionStatus.ROLLING_BACK
            rb = self._rollback.build_execution(
                result,
                reason="Automatic rollback after failure"
                + (" (timeout)" if timed_out else ""),
            )
            rb_result = self._rollback.execute(result, rb)
            result.timeline.rollback_started_at = rb.started_at
            result.timeline.rollback_completed_at = rb.completed_at
            if rb_result.status.value in {"completed", "partial"}:
                result.status = ExecutionStatus.ROLLED_BACK
            else:
                result.status = (
                    ExecutionStatus.TIMED_OUT if timed_out else ExecutionStatus.FAILED
                )
        else:
            result.status = (
                ExecutionStatus.TIMED_OUT if timed_out else ExecutionStatus.FAILED
            )

        result.timeline.completed_at = utc_now()
        self._monitor.recompute_metrics(result)
        event = (
            ExecutionEventType.FAILED
            if result.status
            in {ExecutionStatus.FAILED, ExecutionStatus.TIMED_OUT, ExecutionStatus.ROLLED_BACK}
            else ExecutionEventType.FAILED
        )
        self._monitor.emit(
            result, event, f"Execution ended with status={result.status.value}"
        )
        result.summary = ExecutionSummary(
            headline=f"Execution {result.status.value}",
            details=(
                f"succeeded={result.metrics.succeeded_steps}, "
                f"failed={result.metrics.failed_steps}, "
                f"retries={result.metrics.retry_count}."
            ),
            success=False,
        )
        return result

    def _finalize(
        self, result: ExecutionResult, *, timed_out: bool
    ) -> ExecutionResult:
        self._monitor.recompute_metrics(result)
        if timed_out:
            result.status = ExecutionStatus.TIMED_OUT
            success = False
        elif result.metrics.failed_steps and result.metrics.succeeded_steps:
            if self._allow_partial:
                result.status = ExecutionStatus.PARTIALLY_COMPLETED
                success = False
            else:
                return self._fail_or_rollback(result, timed_out=False)
        elif result.metrics.failed_steps:
            return self._fail_or_rollback(result, timed_out=False)
        else:
            result.status = ExecutionStatus.COMPLETED
            success = True

        result.timeline.completed_at = utc_now()
        self._monitor.emit(
            result,
            ExecutionEventType.COMPLETED if success else ExecutionEventType.FAILED,
            f"Execution finished: {result.status.value}",
        )
        result.summary = ExecutionSummary(
            headline=f"Execution {result.status.value}",
            details=(
                f"All actionable steps processed. "
                f"succeeded={result.metrics.succeeded_steps}/"
                f"{result.metrics.total_steps}."
            ),
            success=success,
        )
        if success or result.status == ExecutionStatus.PARTIALLY_COMPLETED:
            result.verification_request = VerificationRequest(
                execution_id=result.id,
                tenant_id=result.tenant_id,
                plan_id=result.plan_id,
                finding_id=result.finding_id,
                decision_id=result.decision_id,
                asset_id=result.asset_id,
                execution_status=result.status,
                succeeded_step_ids=[
                    s.step_id
                    for s in result.plan.steps
                    if s.status == StepStatus.SUCCEEDED
                ],
            )
        return result
