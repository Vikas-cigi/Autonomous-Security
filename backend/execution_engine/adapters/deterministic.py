"""Deterministic in-process step adapter — no infrastructure side effects."""

from __future__ import annotations

from models.common import utc_now

from execution_engine.domain.enums import StepStatus
from execution_engine.domain.models import (
    ExecutionContext,
    ExecutionStep,
    StepExecutionResult,
)
from execution_engine.interfaces.step_adapter import StepInfrastructureAdapter


class DeterministicRecordingAdapter(StepInfrastructureAdapter):
    """
    Records step execution as succeeded without contacting infrastructure.

    Used for tests and default DI. Inject a real cloud/adapter implementation
    for production provider integrations without changing orchestration logic.

    Deterministic failure hook: metadata key ``force_fail=true`` fails the step.
    """

    def execute_step(
        self,
        step: ExecutionStep,
        *,
        context: ExecutionContext,
        attempt: int,
    ) -> StepExecutionResult:
        started = utc_now()
        force_fail = step.metadata.get("force_fail", "").lower() in {
            "1",
            "true",
            "yes",
        }
        completed = utc_now()
        # Wall clock may be ~0 in tight unit tests; keep a stable positive duration.
        duration = max(1, min(1000, step.timeout_seconds))

        if force_fail:
            return StepExecutionResult(
                step_id=step.step_id,
                sequence=step.sequence,
                status=StepStatus.FAILED,
                attempt=attempt,
                started_at=started,
                completed_at=completed,
                duration_ms=duration,
                message=f"Forced failure for step {step.sequence} ({step.action})",
                error_code="FORCE_FAIL",
                output={
                    "adapter": "deterministic_recording",
                    "tenant_id": str(context.tenant_id),
                    "attempt": str(attempt),
                },
            )

        return StepExecutionResult(
            step_id=step.step_id,
            sequence=step.sequence,
            status=StepStatus.SUCCEEDED,
            attempt=attempt,
            started_at=started,
            completed_at=completed,
            duration_ms=duration,
            message=f"Recorded success for step {step.sequence}: {step.action}",
            output={
                "adapter": "deterministic_recording",
                "target": step.target,
                "tenant_id": str(context.tenant_id),
                "attempt": str(attempt),
            },
        )
