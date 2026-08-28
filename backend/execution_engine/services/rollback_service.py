"""Rollback orchestration for failed or requested rollbacks."""

from __future__ import annotations

from typing import List, Optional

from models.common import new_id, utc_now

from execution_engine.adapters.deterministic import DeterministicRecordingAdapter
from execution_engine.domain.enums import (
    ExecutionEventType,
    RollbackMode,
    RollbackStatus,
    StepStatus,
)
from execution_engine.domain.models import (
    ExecutionResult,
    ExecutionStep,
    RollbackExecution,
    RollbackResult,
    RollbackStep,
    StepExecutionResult,
)
from execution_engine.interfaces.step_adapter import StepInfrastructureAdapter
from execution_engine.services.execution_monitoring import ExecutionMonitoringService


class RollbackService:
    """
    Execute compensating steps. Supports automatic / manual / partial modes.
    Never mutates the original remediation plan snapshot.
    """

    def __init__(
        self,
        adapter: Optional[StepInfrastructureAdapter] = None,
        monitoring: Optional[ExecutionMonitoringService] = None,
    ) -> None:
        self._adapter = adapter or DeterministicRecordingAdapter()
        self._monitor = monitoring or ExecutionMonitoringService()

    def build_execution(
        self,
        result: ExecutionResult,
        *,
        reason: str,
        mode: Optional[RollbackMode] = None,
        only_sequences: Optional[List[int]] = None,
    ) -> RollbackExecution:
        mode = mode or result.rollback_plan.mode
        steps = list(result.rollback_plan.steps)
        if only_sequences is not None:
            allowed = set(only_sequences)
            steps = [
                s
                for s in steps
                if s.compensates_sequence in allowed or s.sequence in allowed
            ]
        # Prefer reverse order of forward success for compensation
        steps = sorted(steps, key=lambda s: s.sequence, reverse=True)
        return RollbackExecution(
            id=new_id(),
            execution_id=result.id,
            status=RollbackStatus.NOT_STARTED,
            mode=mode,
            steps=steps,
            reason=reason,
        )

    def execute(
        self,
        result: ExecutionResult,
        rollback: RollbackExecution,
    ) -> RollbackResult:
        now = utc_now()
        rollback.status = RollbackStatus.IN_PROGRESS
        rollback.started_at = now
        result.rollback_execution = rollback
        self._monitor.emit(
            result,
            ExecutionEventType.ROLLBACK_STARTED,
            rollback.reason or "Rollback started",
        )

        rolled: List[int] = []
        failed: List[int] = []
        step_results: List[StepExecutionResult] = []

        for rb_step in rollback.steps:
            rb_step.status = StepStatus.RUNNING
            # Adapt rollback step to ExecutionStep for adapter contract
            as_step = ExecutionStep(
                step_id=rb_step.step_id,
                sequence=rb_step.sequence,
                action=rb_step.action,
                target=rb_step.target,
                kind="rollback",
                timeout_seconds=rb_step.timeout_seconds,
                max_retries=0,
            )
            step_result = self._adapter.execute_step(
                as_step, context=result.context, attempt=1
            )
            step_results.append(step_result)
            self._monitor.emit(
                result,
                ExecutionEventType.ROLLBACK_STEP,
                step_result.message,
                step_id=rb_step.step_id,
                sequence=rb_step.sequence,
            )
            if step_result.status == StepStatus.SUCCEEDED:
                rb_step.status = StepStatus.SUCCEEDED
                rolled.append(rb_step.sequence)
                # Mark compensated forward steps
                for fwd in result.plan.steps:
                    if (
                        rb_step.compensates_sequence is not None
                        and fwd.sequence == rb_step.compensates_sequence
                    ):
                        fwd.status = StepStatus.ROLLED_BACK
            else:
                rb_step.status = StepStatus.FAILED
                failed.append(rb_step.sequence)
                if rollback.mode != RollbackMode.PARTIAL:
                    break

        rollback.step_results = step_results
        rollback.completed_at = utc_now()

        if failed and not rolled:
            status = RollbackStatus.FAILED
        elif failed and rolled:
            status = RollbackStatus.PARTIAL
        elif not rollback.steps:
            status = RollbackStatus.SKIPPED
        else:
            status = RollbackStatus.COMPLETED

        rollback.status = status
        explanation = (
            f"Rollback {status.value}: rolled={rolled}, failed={failed}."
        )
        if status == RollbackStatus.COMPLETED:
            self._monitor.emit(
                result, ExecutionEventType.ROLLBACK_COMPLETED, explanation
            )
        elif status == RollbackStatus.FAILED:
            self._monitor.emit(
                result, ExecutionEventType.ROLLBACK_FAILED, explanation
            )

        rb_result = RollbackResult(
            status=status,
            rolled_back_sequences=rolled,
            failed_sequences=failed,
            explanation=explanation,
        )
        result.rollback_result = rb_result
        result.rollback_execution = rollback
        return rb_result
