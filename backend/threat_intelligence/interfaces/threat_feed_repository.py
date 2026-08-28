"""ThreatFeedRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from threat_intelligence.domain.enums import ThreatFeedProviderId
from threat_intelligence.domain.models import ThreatFeedMetadata


class ThreatFeedRepository(ABC):
    """Persistence port for feed configuration / sync metadata."""

    @abstractmethod
    def save_feed(
        self,
        feed: ThreatFeedMetadata,
        *,
        actor: Optional[str] = None,
    ) -> ThreatFeedMetadata:
        ...

    @abstractmethod
    def get_feed(self, feed_id: UUID) -> ThreatFeedMetadata:
        ...

    @abstractmethod
    def list_feeds(
        self,
        *,
        tenant_id: Optional[UUID] = None,
        provider: Optional[ThreatFeedProviderId] = None,
        enabled_only: bool = False,
        include_global: bool = True,
    ) -> List[ThreatFeedMetadata]:
        ...

    @abstractmethod
    def find_by_provider(
        self,
        provider: ThreatFeedProviderId,
        *,
        tenant_id: Optional[UUID] = None,
    ) -> Optional[ThreatFeedMetadata]:
        ...
