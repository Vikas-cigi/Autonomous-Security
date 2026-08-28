"""Execute individual remediation steps with retry/timeout handling."""

from __future__ import annotations

from typing import Optional

from execution_engine.adapters.deterministic import DeterministicRecordingAdapter
from execution_engine.domain.enums import ExecutionEventType, StepStatus
from execution_engine.domain.models import (
    ExecutionResult,
    ExecutionStep,
    StepExecutionResult,
)
from execution_engine.interfaces.step_adapter import StepInfrastructureAdapter
from execution_engine.services.execution_monitoring import ExecutionMonitoringService


class ExecutionStepExecutor:
    """
    Runs one step via StepInfrastructureAdapter with retries.

    Timeout is enforced as a policy on the step contract; the default adapter
    is synchronous/deterministic. Real adapters may honor timeout_seconds.
    """

    def __init__(
        self,
        adapter: Optional[StepInfrastructureAdapter] = None,
        monitoring: Optional[ExecutionMonitoringService] = None,
    ) -> None:
        self._adapter = adapter or DeterministicRecordingAdapter()
        self._monitor = monitoring or ExecutionMonitoringService()

    def execute(
        self,
        result: ExecutionResult,
        step: ExecutionStep,
    ) -> StepExecutionResult:
        max_attempts = step.max_retries + 1
        last: Optional[StepExecutionResult] = None

        for attempt in range(1, max_attempts + 1):
            step.status = StepStatus.RUNNING
            step.attempt = attempt
            self._monitor.emit(
                result,
                ExecutionEventType.STEP_STARTED,
                f"Starting step {step.sequence} attempt {attempt}",
                step_id=step.step_id,
                sequence=step.sequence,
            )
            step_result = self._adapter.execute_step(
                step, context=result.context, attempt=attempt
            )
            last = step_result

            if step_result.status == StepStatus.SUCCEEDED:
                step.status = StepStatus.SUCCEEDED
                self._monitor.emit(
                    result,
                    ExecutionEventType.STEP_SUCCEEDED,
                    step_result.message,
                    step_id=step.step_id,
                    sequence=step.sequence,
                )
                return step_result

            if attempt < max_attempts:
                self._monitor.emit(
                    result,
                    ExecutionEventType.STEP_RETRY,
                    f"Retrying step {step.sequence} after failure",
                    step_id=step.step_id,
                    sequence=step.sequence,
                    details={"attempt": attempt, "error": step_result.error_code},
                )
                continue

            step.status = step_result.status
            if step_result.status == StepStatus.TIMED_OUT:
                self._monitor.emit(
                    result,
                    ExecutionEventType.STEP_TIMEOUT,
                    step_result.message,
                    step_id=step.step_id,
                    sequence=step.sequence,
                )
            else:
                self._monitor.emit(
                    result,
                    ExecutionEventType.STEP_FAILED,
                    step_result.message,
                    step_id=step.step_id,
                    sequence=step.sequence,
                )
            return step_result

        assert last is not None
        return last
