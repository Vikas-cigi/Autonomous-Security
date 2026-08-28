"""
Provider Factory — Architecture V2 provider resolution.

Resolves a provider name to a ``BaseProvider`` instance. Not wired into
``LLMService`` or FastAPI in this phase.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Mapping, Optional

from providers.anthropic_provider import AnthropicProvider
from providers.base_provider import BaseProvider
from providers.exceptions import UnknownProviderError
from providers.llama_provider import LlamaProvider
from providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """
    Creates / looks up LLM providers by name.

    SOLID notes:
        - Single Responsibility: provider registry and lookup only.
        - Open/Closed: register new providers via DI without editing callers.
        - Dependency Inversion: returns ``BaseProvider``, not concrete types.

    Lifecycle:
        1. Construct factory with defaults or an injected registry.
        2. Call ``get_provider(name)`` per request (or cache the instance).
        3. Call ``await provider.generate(prompt)``.
        4. Providers are long-lived and reusable; the factory does not close
           HTTP clients today (callers / future lifespan hooks may).
    """

    def __init__(
        self,
        providers: Optional[Mapping[str, BaseProvider]] = None,
        *,
        default_provider: str = "llama",
    ) -> None:
        """
        Args:
            providers: Optional name → instance map. When omitted, registers
                ``llama`` (working), ``openai`` and ``anthropic`` (placeholders).
            default_provider: Name returned by ``get_default_provider``.
        """

        self._providers: Dict[str, BaseProvider] = {
            key.lower(): value
            for key, value in (providers or self.default_registry()).items()
        }
        self._default_provider = default_provider.lower()

        if self._default_provider not in self._providers:
            raise UnknownProviderError(
                f"Default provider '{self._default_provider}' is not registered.",
                provider=self._default_provider,
                details={"registered": sorted(self._providers.keys())},
            )

        logger.debug(
            "ProviderFactory initialized default=%s registered=%s",
            self._default_provider,
            sorted(self._providers.keys()),
        )

    @staticmethod
    def default_registry() -> Dict[str, BaseProvider]:
        """Return the phase-0 provider registry."""

        return {
            "llama": LlamaProvider(),
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
        }

    @property
    def registered_names(self) -> tuple[str, ...]:
        """Sorted tuple of registered provider names."""

        return tuple(sorted(self._providers.keys()))

    def register(self, name: str, provider: BaseProvider) -> None:
        """
        Register or replace a provider instance (for tests / plugins).

        Args:
            name: Lookup key (case-insensitive).
            provider: Concrete ``BaseProvider`` implementation.
        """

        key = name.lower().strip()
        self._providers[key] = provider
        logger.info(
            "ProviderFactory registered name=%s class=%s",
            key,
            type(provider).__name__,
        )

    def get_provider(self, provider_name: str) -> BaseProvider:
        """
        Resolve a provider by name.

        Args:
            provider_name: Registry key (e.g. ``llama``, ``openai``).

        Returns:
            BaseProvider: Registered instance.

        Raises:
            UnknownProviderError: If the name is not registered.
        """

        key = (provider_name or "").lower().strip()
        provider = self._providers.get(key)
        if provider is None:
            logger.error(
                "ProviderFactory unknown provider=%s registered=%s",
                key,
                sorted(self._providers.keys()),
            )
            raise UnknownProviderError(
                f"Unknown provider '{provider_name}'.",
                provider=key or None,
                details={"registered": sorted(self._providers.keys())},
            )

        logger.info(
            "ProviderFactory.get_provider name=%s class=%s",
            key,
            type(provider).__name__,
        )
        return provider

    def get_default_provider(self) -> BaseProvider:
        """Return the configured default provider instance."""

        return self.get_provider(self._default_provider)

    def available_providers(self) -> Iterable[str]:
        """Iterate registered provider names."""

        return self.registered_names
