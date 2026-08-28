"""Domain enums for the Enterprise Execution Engine."""

from __future__ import annotations

from enum import Enum


class ExecutionStatus(str, Enum):
    """Lifecycle state of an execution run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    PARTIALLY_COMPLETED = "partially_completed"


class StepStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class RollbackMode(str, Enum):
    NONE = "none"
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    PARTIAL = "partial"


class RollbackStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class ExecutionEventType(str, Enum):
    CREATED = "created"
    STARTED = "started"
    STEP_STARTED = "step_started"
    STEP_SUCCEEDED = "step_succeeded"
    STEP_FAILED = "step_failed"
    STEP_RETRY = "step_retry"
    STEP_TIMEOUT = "step_timeout"
    PAUSED = "paused"
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK_STARTED = "rollback_started"
    ROLLBACK_STEP = "rollback_step"
    ROLLBACK_COMPLETED = "rollback_completed"
    ROLLBACK_FAILED = "rollback_failed"
    REPLAYED = "replayed"


class AuditAction(str, Enum):
    EXECUTION_CREATED = "execution_created"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_RESUMED = "execution_resumed"
    EXECUTION_TIMED_OUT = "execution_timed_out"
    STEP_EXECUTED = "step_executed"
    STEP_RETRY = "step_retry"
    ROLLBACK_STARTED = "rollback_started"
    ROLLBACK_COMPLETED = "rollback_completed"
    ROLLBACK_FAILED = "rollback_failed"
    SEARCHED = "searched"
    HISTORY_RECORDED = "history_recorded"
    REPLAYED = "replayed"
