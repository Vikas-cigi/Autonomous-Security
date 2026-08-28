"""
Anthropic provider — Architecture V2 placeholder.

Not wired to the Anthropic SDK or HTTP API yet. ``generate`` raises
``ProviderNotImplementedError`` so accidental use fails loudly.
"""

from __future__ import annotations

import logging
from typing import Optional

from prompt.models import Prompt
from providers.base_provider import BaseProvider
from providers.exceptions import ProviderNotImplementedError
from providers.models import AIResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """
    Placeholder Anthropic Messages API provider.

    Args:
        api_key: Reserved for future credential injection.
        model_name: Reserved default model id (e.g. ``claude-sonnet-4-5``).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "claude-sonnet-4-5",
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        logger.debug(
            "AnthropicProvider placeholder initialized model=%s api_key_set=%s",
            self.model_name,
            bool(api_key),
        )

    @property
    def provider_name(self) -> str:
        """Return the factory key for this provider."""

        return "anthropic"

    async def generate(self, prompt: Prompt) -> AIResponse:
        """
        Placeholder — not implemented.

        Raises:
            ProviderNotImplementedError: Always, until Anthropic wiring lands.
        """

        logger.warning(
            "AnthropicProvider.generate called but not implemented "
            "(message_count=%s)",
            len(prompt.messages),
        )
        raise ProviderNotImplementedError(
            "AnthropicProvider is a scaffold placeholder and is not implemented yet.",
            provider=self.provider_name,
            details={"model": self.model_name},
        )
