"""
Adapter configuration models shared by all tool adapters.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdapterConfig(BaseModel):
    """
    Runtime configuration for a security tool adapter.

    Tool-specific subclasses may extend this model; the base fields cover
    authentication, timeouts, retries, and binary location.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    tool_name: str = Field(..., min_length=1, max_length=128)
    binary_path: str = Field(
        ...,
        min_length=1,
        description="Filesystem path or PATH name of the scanner binary.",
    )
    timeout_seconds: float = Field(default=300.0, gt=0.0, le=86_400.0)
    max_retries: int = Field(default=1, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=1.0, ge=0.0, le=60.0)
    working_directory: Optional[str] = Field(default=None)
    environment: Dict[str, str] = Field(
        default_factory=dict,
        description="Extra environment variables for the subprocess.",
    )
    default_args: List[str] = Field(default_factory=list)
    api_token: Optional[str] = Field(
        default=None,
        description="Optional API token / cloud credential reference.",
    )
    verify_tls: bool = Field(default=True)
    enabled: bool = Field(default=True)

    @field_validator("environment")
    @classmethod
    def limit_env(cls, value: Dict[str, str]) -> Dict[str, str]:
        """Prevent unbounded environment injection."""

        if len(value) > 64:
            raise ValueError("environment limited to 64 entries")
        return value

    @field_validator("default_args")
    @classmethod
    def limit_args(cls, value: List[str]) -> List[str]:
        """Bound default argument list size."""

        if len(value) > 128:
            raise ValueError("default_args limited to 128 entries")
        return value
