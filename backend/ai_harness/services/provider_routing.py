"""AIProviderRoutingService — select primary + fallback providers."""

from __future__ import annotations

from typing import List, Optional, Sequence

from providers.base_provider import BaseProvider
from providers.exceptions import UnknownProviderError
from providers.provider_factory import ProviderFactory

from ai_harness.domain.weights import DEFAULT_FALLBACK_ORDER
from ai_harness.exceptions import InvalidAIRequestError


class AIProviderRoutingService:
    """
    Resolve an ordered provider chain without embedding business logic.

    Reuses ProviderFactory; does not instantiate HTTP clients itself.
    """

    def __init__(self, provider_factory: Optional[ProviderFactory] = None) -> None:
        self._factory = provider_factory or ProviderFactory()

    @property
    def factory(self) -> ProviderFactory:
        return self._factory

    def resolve_chain(
        self,
        *,
        provider_name: Optional[str] = None,
        fallback_providers: Optional[Sequence[str]] = None,
    ) -> List[str]:
        if provider_name:
            primary = provider_name.lower().strip()
        else:
            primary = self._factory.get_default_provider().provider_name.lower().strip()
        chain: List[str] = [primary]
        fallbacks = list(fallback_providers or [])
        if not fallbacks:
            fallbacks = [p for p in DEFAULT_FALLBACK_ORDER if p != primary]
        for name in fallbacks:
            key = name.lower().strip()
            if key and key not in chain:
                chain.append(key)
        return chain

    def get_provider(self, name: str) -> BaseProvider:
        try:
            return self._factory.get_provider(name)
        except UnknownProviderError as exc:
            raise InvalidAIRequestError(
                f"Unknown provider '{name}'",
                details={"provider": name, "registered": list(self._factory.registered_names)},
            ) from exc
