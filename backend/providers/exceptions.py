"""
Provider-layer exceptions for Architecture V2.

Hierarchy is intentionally narrow so callers can catch ``ProviderError``
broadly or handle provider-specific failures precisely.
"""

from __future__ import annotations

from typing import Any, Optional


class ProviderError(Exception):
    """Base error for all provider-factory and provider failures."""

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        details: Optional[Any] = None,
    ) -> None:
        self.provider = provider
        self.details = details
        super().__init__(message)


class UnknownProviderError(ProviderError):
    """Raised when ProviderFactory cannot resolve a provider name."""


class ProviderNotImplementedError(ProviderError):
    """Raised by placeholder providers that are not yet wired to a backend."""


class ProviderConfigurationError(ProviderError):
    """Raised when required settings / credentials are missing or invalid."""


class ProviderRequestError(ProviderError):
    """Raised when the upstream HTTP / SDK call fails at the transport layer."""


class ProviderResponseError(ProviderError):
    """Raised when the upstream response is malformed or empty."""


class LlamaProviderError(ProviderError):
    """Errors specific to the llama.cpp / local OpenAI-compatible provider."""


class OpenAIProviderError(ProviderError):
    """Errors specific to the OpenAI provider."""


class AnthropicProviderError(ProviderError):
    """Errors specific to the Anthropic provider."""
