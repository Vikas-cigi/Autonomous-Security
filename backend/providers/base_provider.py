"""
Abstract LLM provider contract for Architecture V2.

V1 note:
    ``LLMService`` still calls ``LlamaProvider.chat`` / ``stream_chat``
    directly. Those legacy methods remain on ``LlamaProvider`` and are
    intentionally **not** part of this V2 abstract surface so placeholders
    are not forced to implement them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from prompt.models import Prompt
from providers.models import AIResponse


class BaseProvider(ABC):
    """
    Interface for Architecture V2 LLM providers.

    SOLID notes:
        - Single Responsibility: talk to one upstream model API.
        - Open/Closed: new providers subclass this without changing the factory.
        - Liskov: all providers honor ``generate(prompt) -> AIResponse``.
        - Dependency Inversion: LLMService (future) and ProviderFactory depend
          on this abstraction, not concrete SDKs.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable provider id used by ``ProviderFactory`` (e.g. ``llama``)."""

    @abstractmethod
    async def generate(self, prompt: Prompt) -> AIResponse:
        """
        Generate a completion from a provider-ready ``Prompt``.

        Args:
            prompt: Output of PromptBuilder (messages + optional hints).

        Returns:
            AIResponse: Normalized completion result.

        Raises:
            ProviderError: On configuration, transport, or response failures.
        """
