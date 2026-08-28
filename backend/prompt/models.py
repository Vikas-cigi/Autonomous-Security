"""
Domain models for the Prompt Builder layer.

``Prompt`` is the provider-ready payload produced from ``AIContext``.
Kept free of FastAPI and concrete provider SDKs so templates stay
independently unit-testable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PromptMessage(BaseModel):
    """A single chat-completion message in OpenAI-compatible shape."""

    role: str = Field(..., description="Message role: system | user | assistant | tool.")
    content: str = Field(..., description="Message body.")


class ProviderHints(BaseModel):
    """
    Optional knobs forwarded to ProviderFactory / LLM providers later.

    Phase 0 leaves these unset; templates may populate defaults.
    """

    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    stop: Optional[List[str]] = None
    stream: Optional[bool] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class Prompt(BaseModel):
    """
    Fully assembled prompt ready for an LLM provider.

    Attributes:
        system_prompt: Canonical system instruction text (also mirrored as
            the first system message when present).
        messages: Ordered chat messages including system / history / user.
        metadata: Template name, decision type, diagnostics.
        provider_hints: Optional generation parameters for the provider layer.
    """

    system_prompt: str = Field(
        default="",
        description="System instruction text used for this completion.",
    )
    messages: List[PromptMessage] = Field(
        default_factory=list,
        description="Ordered OpenAI-compatible chat messages.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Assembly diagnostics and template signals.",
    )
    provider_hints: ProviderHints = Field(
        default_factory=ProviderHints,
        description="Optional provider generation hints.",
    )

    def as_openai_messages(self) -> List[Dict[str, str]]:
        """
        Return messages as plain dicts for OpenAI-compatible HTTP APIs.

        Convenience for future ProviderFactory integration; not used at runtime yet.
        """

        return [{"role": m.role, "content": m.content} for m in self.messages]
