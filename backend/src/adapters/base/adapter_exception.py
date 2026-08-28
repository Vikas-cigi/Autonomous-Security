"""
Adapter framework exceptions.

Structured, catchable errors for authentication, policy, scope, execution,
timeout, and parsing failures.
"""

from __future__ import annotations

from typing import Any, Optional


class AdapterError(Exception):
    """Base error for all adapter framework failures."""

    def __init__(
        self,
        message: str,
        *,
        tool_name: Optional[str] = None,
        details: Optional[Any] = None,
    ) -> None:
        self.tool_name = tool_name
        self.details = details
        super().__init__(message)


class AdapterAuthenticationError(AdapterError):
    """Raised when tool or cloud credentials cannot be validated."""


class AdapterPolicyViolationError(AdapterError):
    """Raised when PolicyEngine denies or blocks execution."""


class AdapterScopeViolationError(AdapterError):
    """Raised when tenant/asset/scope/target constraints are violated."""


class AdapterExecutionError(AdapterError):
    """Raised when the underlying scanner process fails unexpectedly."""


class AdapterTimeoutError(AdapterError):
    """Raised when scanner execution exceeds the configured timeout."""


class AdapterParserError(AdapterError):
    """Raised when stdout/stderr/raw output cannot be parsed safely."""


class AdapterConfigurationError(AdapterError):
    """Raised when adapter configuration is incomplete or invalid."""


class AdapterNotFoundError(AdapterError):
    """Raised when the registry cannot resolve a tool adapter."""
