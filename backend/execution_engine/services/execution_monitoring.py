"""Execution monitoring — progress, metrics, events, logs."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from models.common import new_id, utc_now

from execution_engine.domain.enums import ExecutionEventType, StepStatus
from execution_engine.domain.models import (
    ExecutionEvent,
    ExecutionLog,
    ExecutionMetrics,
    ExecutionResult,
)


class ExecutionMonitoringService:
    """Append events/logs and recompute metrics. Hook-friendly, no side I/O."""

    def emit(
        self,
        result: ExecutionResult,
        event_type: ExecutionEventType,
        message: str,
        *,
        step_id: Optional[UUID] = None,
        sequence: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ExecutionEvent:
        event = ExecutionEvent(
            id=new_id(),
            execution_id=result.id,
            event_type=event_type,
            message=message,
            step_id=step_id,
            sequence=sequence,
            details=details or {},
            created_at=utc_now(),
        )
        result.events = list(result.events) + [event]
        return event

    def log(
        self,
        result: ExecutionResult,
        message: str,
        *,
        level: str = "info",
        step_id: Optional[UUID] = None,
    ) -> ExecutionLog:
        entry = ExecutionLog(
            id=new_id(),
            execution_id=result.id,
            level=level,
            message=message,
            step_id=step_id,
            created_at=utc_now(),
        )
        result.logs = list(result.logs) + [entry]
        return entry

    def recompute_metrics(self, result: ExecutionResult) -> ExecutionMetrics:
        succeeded = sum(
            1 for r in result.step_results if r.status == StepStatus.SUCCEEDED
        )
        failed = sum(1 for r in result.step_results if r.status == StepStatus.FAILED)
        skipped = sum(1 for r in result.step_results if r.status == StepStatus.SKIPPED)
        retries = sum(max(0, r.attempt - 1) for r in result.step_results)
        duration = sum(r.duration_ms for r in result.step_results)
        rb_duration = 0
        if result.rollback_execution:
            rb_duration = sum(
                r.duration_ms for r in result.rollback_execution.step_results
            )
        metrics = ExecutionMetrics(
            total_steps=len(result.plan.steps),
            succeeded_steps=succeeded,
            failed_steps=failed,
            skipped_steps=skipped,
            retry_count=retries,
            duration_ms=duration,
            rollback_duration_ms=rb_duration,
            resource_metadata={
                "queue": result.context.queue_name,
                "mode": result.plan.mode.value,
            },
        )
        result.metrics = metrics
        return metrics
