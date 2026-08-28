"""
Normalization-layer exceptions.

Raised when raw tool payloads cannot be trusted or converted into canonical
``SecurityFindingObject`` instances.
"""

from __future__ import annotations

from typing import Any, Optional


class NormalizationError(Exception):
    """Base error for the normalization service."""

    def __init__(
        self,
        message: str,
        *,
        tool: Optional[str] = None,
        details: Optional[Any] = None,
    ) -> None:
        self.tool = tool
        self.details = details
        super().__init__(message)


class UnknownToolError(NormalizationError):
    """No adapter is registered for the requested tool."""


class MalformedInputError(NormalizationError):
    """Raw payload failed schema / shape validation."""


class NormalizationItemError(NormalizationError):
    """A single finding within a batch failed normalization."""
