"""
RawResult — sole outbound contract of every security tool adapter.

Adapters MUST NOT construct ``SecurityFindingObject``. Downstream systems
pass ``raw_output`` into the Normalization Service.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.common import utc_now


class RawResultStatus(str, Enum):
    """Terminal status of an adapter execution."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    POLICY_DENIED = "policy_denied"
    SCOPE_DENIED = "scope_denied"
    AUTH_FAILED = "auth_failed"


class RawResult(BaseModel):
    """
    Immutable-leaning capture of a single scanner invocation.

    ``raw_output`` holds the vendor payload (dict/list/str). Normalization
    consumes it; adapters never interpret it into canonical findings.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    execution_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(..., description="Tenant that owns this execution.")
    tool_name: str = Field(..., min_length=1, max_length=128)
    tool_version: str = Field(default="unknown", max_length=128)
    execution_time_ms: float = Field(..., ge=0.0)
    started_at: datetime = Field(...)
    completed_at: datetime = Field(default_factory=utc_now)
    status: RawResultStatus = Field(...)
    exit_code: Optional[int] = Field(default=None)
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    raw_output: Any = Field(
        default=None,
        description="Parsed vendor JSON when available; otherwise None.",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    scope: Dict[str, Any] = Field(default_factory=dict)
    asset: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware timestamps."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @field_validator("tags", "errors", "warnings")
    @classmethod
    def bound_string_lists(cls, value: List[str]) -> List[str]:
        """Cap diagnostic list sizes."""

        if len(value) > 500:
            raise ValueError("list limited to 500 entries")
        return value

    @model_validator(mode="after")
    def completed_after_started(self) -> RawResult:
        """Guarantee temporal consistency."""

        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self

    @property
    def succeeded(self) -> bool:
        """True when the scanner completed successfully."""

        return self.status == RawResultStatus.SUCCEEDED
