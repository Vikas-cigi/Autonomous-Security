"""
Domain models for the Provider Factory layer (Architecture V2).

``AIResponse`` is the normalized completion result returned by every
``BaseProvider.generate`` implementation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """
    Normalized token usage counters.

    Extra upstream keys may also appear on ``AIResponse.usage`` as a plain
    dict; this model is available when callers want structured access.
    """

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class AIResponse(BaseModel):
    """
    Normalized LLM completion result.

    Attributes:
        text: Assistant-visible completion text.
        provider: Provider identifier (e.g. ``llama``, ``openai``).
        model: Model name reported or configured for the call.
        usage: Upstream usage object (token counts, etc.).
        finish_reason: Why generation stopped (``stop``, ``length``, …).
        metadata: Latency, raw ids, and other diagnostics.
    """

    text: str = Field(..., description="Generated assistant text.")
    provider: str = Field(..., description="Provider that produced the response.")
    model: str = Field(..., description="Model id / display name.")
    usage: Dict[str, Any] = Field(
        default_factory=dict,
        description="Token usage and related counters from the upstream API.",
    )
    finish_reason: Optional[str] = Field(
        default=None,
        description="Upstream finish / stop reason when available.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostics (latency_ms, request ids, etc.).",
    )
