"""Threat feed provider abstraction (no live API calls)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from threat_intelligence.domain.enums import FeedSyncStatus, ThreatFeedProviderId
from threat_intelligence.domain.ioc import IndicatorOfCompromise
from threat_intelligence.domain.models import CVERecord, MITRETechnique, ThreatFeedMetadata


@dataclass
class FeedSyncRequest:
    """Input for a feed sync operation."""

    feed: ThreatFeedMetadata
    tenant_id: Optional[UUID] = None
    full_refresh: bool = False
    limit: Optional[int] = None


@dataclass
class FeedSyncResult:
    """Outcome of a (placeholder or real) feed sync."""

    provider: ThreatFeedProviderId
    status: FeedSyncStatus
    message: str
    cves: List[CVERecord] = field(default_factory=list)
    iocs: List[IndicatorOfCompromise] = field(default_factory=list)
    techniques: List[MITRETechnique] = field(default_factory=list)
    records_fetched: int = 0
    cursor: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class ThreatFeedProvider(ABC):
    """
    Port for external / internal threat feed connectors.

    Implementations must not change business services; register via
    ``ThreatFeedProviderRegistry``.
    """

    @property
    @abstractmethod
    def provider_id(self) -> ThreatFeedProviderId:
        """Stable provider identity."""

    @abstractmethod
    def sync(self, request: FeedSyncRequest) -> FeedSyncResult:
        """
        Pull or transform feed data.

        Placeholder providers return ``FeedSyncStatus.SKIPPED`` without I/O.
        """

    def health_check(self) -> bool:
        """Optional connectivity probe; placeholders return False."""

        return False


class PlaceholderThreatFeedProvider(ThreatFeedProvider):
    """Base for future connectors — no external API integration."""

    def __init__(self, provider_id: ThreatFeedProviderId) -> None:
        self._provider_id = provider_id

    @property
    def provider_id(self) -> ThreatFeedProviderId:
        return self._provider_id

    def sync(self, request: FeedSyncRequest) -> FeedSyncResult:
        return FeedSyncResult(
            provider=self.provider_id,
            status=FeedSyncStatus.SKIPPED,
            message=(
                f"Provider '{self.provider_id.value}' is a placeholder; "
                "external API integration not enabled."
            ),
            cursor=request.feed.cursor,
            details={"full_refresh": request.full_refresh},
        )


class ThreatFeedProviderRegistry:
    """In-process registry of feed providers (Open/Closed)."""

    def __init__(self) -> None:
        self._providers: Dict[ThreatFeedProviderId, ThreatFeedProvider] = {}

    def register(self, provider: ThreatFeedProvider) -> None:
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: ThreatFeedProviderId) -> ThreatFeedProvider:
        if provider_id not in self._providers:
            raise KeyError(f"No provider registered for {provider_id.value}")
        return self._providers[provider_id]

    def list_providers(self) -> Sequence[ThreatFeedProvider]:
        return list(self._providers.values())

    def has(self, provider_id: ThreatFeedProviderId) -> bool:
        return provider_id in self._providers
