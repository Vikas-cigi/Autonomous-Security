"""Domain enums for the Enterprise AI Harness."""

from __future__ import annotations

from enum import Enum


class AIExecutionStatus(str, Enum):
    """Lifecycle status of a harness execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    VALIDATION_FAILED = "validation_failed"
    CANCELLED = "cancelled"


class ValidationSeverity(str, Enum):
    """Severity of a validation finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ReflectionMode(str, Enum):
    """Whether / how a reflection pass runs."""

    DISABLED = "disabled"
    ON_FAILURE = "on_failure"
    ALWAYS = "always"


class ConfidenceBand(str, Enum):
    """Coarse confidence band for harness outputs."""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class AuditAction(str, Enum):
    """Audit actions for AI Harness operations."""

    EXECUTION_STARTED = "execution_started"
    PROVIDER_SELECTED = "provider_selected"
    PROVIDER_FALLBACK = "provider_fallback"
    CONTEXT_BUILT = "context_built"
    PROMPT_BUILT = "prompt_built"
    PROVIDER_INVOKED = "provider_invoked"
    RETRY_ATTEMPTED = "retry_attempted"
    VALIDATION_COMPLETED = "validation_completed"
    REFLECTION_COMPLETED = "reflection_completed"
    EXECUTION_SUCCEEDED = "execution_succeeded"
    EXECUTION_FAILED = "execution_failed"
    SEARCHED = "searched"
    HISTORY_RECORDED = "history_recorded"
