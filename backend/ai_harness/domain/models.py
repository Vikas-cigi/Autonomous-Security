"""Core Enterprise AI Harness domain models.

These models are harness-governance envelopes. They are distinct from
``providers.models.AIResponse`` (raw provider completion).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from ai_harness.domain.enums import (
    AIExecutionStatus,
    ConfidenceBand,
    ReflectionMode,
    ValidationSeverity,
)


class AIConfidence(FortiBaseModel):
    """Harness-evaluated confidence for an AI output."""

    score: float = Field(..., ge=0.0, le=1.0)
    band: ConfidenceBand = Field(...)
    signals: List[str] = Field(default_factory=list)
    explanation: str = Field(..., min_length=1, max_length=2000)


class AIUsageMetrics(FortiBaseModel):
    """Token and cost tracking for one provider call or full execution."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    provider: Optional[str] = Field(default=None, max_length=64)
    model: Optional[str] = Field(default=None, max_length=128)


class AIValidationIssue(FortiBaseModel):
    """Single validation finding against structured AI output."""

    code: str = Field(..., min_length=1, max_length=64)
    severity: ValidationSeverity = Field(...)
    message: str = Field(..., min_length=1, max_length=2000)
    path: Optional[str] = Field(default=None, max_length=256)


class AIValidationResult(FortiBaseModel):
    """Outcome of structured-output / schema validation."""

    valid: bool = Field(...)
    issues: List[AIValidationIssue] = Field(default_factory=list)
    parsed_payload: Optional[Dict[str, Any]] = None
    schema_name: Optional[str] = Field(default=None, max_length=128)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)


class AIReflection(FortiBaseModel):
    """Optional second-pass reflection over a primary AI response."""

    enabled: bool = Field(default=False)
    performed: bool = Field(default=False)
    improved: bool = Field(default=False)
    reflection_text: Optional[str] = Field(default=None, max_length=16000)
    notes: str = Field(default="", max_length=2000)


class AIProviderResult(FortiBaseModel):
    """Normalized result from a single provider attempt."""

    provider: str = Field(..., min_length=1, max_length=64)
    model: str = Field(default="unknown", max_length=128)
    text: str = Field(default="", max_length=32000)
    finish_reason: Optional[str] = Field(default=None, max_length=64)
    usage: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = Field(default=0.0, ge=0.0)
    attempt: int = Field(default=1, ge=1)
    success: bool = Field(default=True)
    error: Optional[str] = Field(default=None, max_length=2000)


class AIRequest(FortiBaseModel):
    """
    Harness input for one AI interaction.

    Contains no cybersecurity business rules — only orchestration knobs and
    the message / optional system prompt / schema for validation.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    correlation_id: Optional[UUID] = Field(
        default=None,
        description="Optional upstream correlation (decision_id, plan_id, …).",
    )
    session_id: Optional[str] = Field(default=None, max_length=128)
    message: str = Field(..., min_length=1, max_length=16000)
    system_prompt: Optional[str] = Field(default=None, max_length=16000)
    provider_name: Optional[str] = Field(default=None, max_length=64)
    fallback_providers: List[str] = Field(default_factory=list)
    expect_json: bool = Field(default=False)
    json_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional JSON Schema (draft-07 subset) for structured output.",
    )
    schema_name: Optional[str] = Field(default=None, max_length=128)
    required_json_keys: List[str] = Field(default_factory=list)
    reflection_mode: ReflectionMode = Field(default=ReflectionMode.DISABLED)
    max_retries: int = Field(default=2, ge=0, le=5)
    timeout_seconds: float = Field(default=60.0, gt=0.0, le=600.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    actor: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @field_validator("fallback_providers", "required_json_keys")
    @classmethod
    def limit_lists(cls, value: list) -> list:
        if len(value) > 16:
            raise ValueError("list limited to 16 entries")
        return value


class AIResponse(FortiBaseModel):
    """Harness-normalized AI response after validation / reflection."""

    id: UUID = Field(default_factory=new_id)
    request_id: UUID = Field(...)
    text: str = Field(default="", max_length=32000)
    provider: str = Field(..., min_length=1, max_length=64)
    model: str = Field(default="unknown", max_length=128)
    finish_reason: Optional[str] = None
    structured_payload: Optional[Dict[str, Any]] = None
    confidence: Optional[AIConfidence] = None
    usage: AIUsageMetrics = Field(default_factory=AIUsageMetrics)
    validation: Optional[AIValidationResult] = None
    reflection: Optional[AIReflection] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIExecution(TimestampedModel):
    """Persisted execution envelope for one harness run."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    request_id: UUID = Field(...)
    correlation_id: Optional[UUID] = None
    status: AIExecutionStatus = Field(default=AIExecutionStatus.PENDING)
    primary_provider: Optional[str] = Field(default=None, max_length=64)
    selected_provider: Optional[str] = Field(default=None, max_length=64)
    attempt_count: int = Field(default=0, ge=0)
    provider_results: List[AIProviderResult] = Field(default_factory=list)
    request_snapshot: Dict[str, Any] = Field(default_factory=dict)
    algorithm_version: str = Field(default="1.0.0", min_length=1, max_length=32)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class AIExecutionResult(FortiBaseModel):
    """Full harness outcome returned to callers."""

    execution: AIExecution = Field(...)
    request: AIRequest = Field(...)
    response: Optional[AIResponse] = None
    success: bool = Field(...)
    status: AIExecutionStatus = Field(...)
    error_message: Optional[str] = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def sync_status(self) -> AIExecutionResult:
        if self.status != self.execution.status:
            object.__setattr__(self, "status", self.execution.status)
        return self


class AIAuditRecord(FortiBaseModel):
    """Append-only audit entry for harness lifecycle events."""

    id: UUID = Field(default_factory=new_id)
    execution_id: Optional[UUID] = None
    request_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    action: str = Field(..., min_length=1, max_length=64)
    actor: Optional[str] = Field(default=None, max_length=256)
    message: str = Field(..., min_length=1, max_length=4000)
    details: Dict[str, Any] = Field(default_factory=dict)
    provider: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value
