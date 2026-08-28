"""
Policy Engine exceptions.
"""

from __future__ import annotations

from typing import Any, Optional


class PolicyEngineError(Exception):
    """Base error for policy evaluation failures."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Any] = None,
    ) -> None:
        self.details = details
        super().__init__(message)


class PolicyConfigurationError(PolicyEngineError):
    """Raised when the engine has no usable policy source."""


class PolicyEvaluationError(PolicyEngineError):
    """Raised when evaluation cannot complete safely (fail closed upstream)."""
