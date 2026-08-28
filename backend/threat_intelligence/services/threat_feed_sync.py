"""Threat feed sync orchestration over provider abstractions."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from models.common import utc_now
from threat_intelligence.domain.enums import AuditAction, FeedSyncStatus
from threat_intelligence.domain.models import ThreatFeedMetadata
from threat_intelligence.interfaces.ioc_repository import IOCRepository
from threat_intelligence.interfaces.threat_feed_repository import ThreatFeedRepository
from threat_intelligence.interfaces.threat_intel_repository import ThreatIntelRepository
from threat_intelligence.providers.base import (
    FeedSyncRequest,
    FeedSyncResult,
    ThreatFeedProviderRegistry,
)
from threat_intelligence.services.audit import AuditLogger


class ThreatFeedSyncService:
    """
    Sync threat feeds through registered providers.

    Placeholder providers return SKIPPED without external I/O. When real
    connectors are added, this service persists returned CVEs/IOCs without
    changing its public contract.
    """

    def __init__(
        self,
        feed_repository: ThreatFeedRepository,
        provider_registry: ThreatFeedProviderRegistry,
        *,
        intel_repository: Optional[ThreatIntelRepository] = None,
        ioc_repository: Optional[IOCRepository] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._feeds = feed_repository
        self._providers = provider_registry
        self._intel = intel_repository
        self._iocs = ioc_repository
        self._audit = audit_logger

    def register_feed(
        self,
        feed: ThreatFeedMetadata,
        *,
        actor: Optional[str] = None,
    ) -> ThreatFeedMetadata:
        return self._feeds.save_feed(feed, actor=actor)

    def sync_feed(
        self,
        feed_id: UUID,
        *,
        tenant_id: Optional[UUID] = None,
        full_refresh: bool = False,
        actor: Optional[str] = None,
    ) -> FeedSyncResult:
        feed = self._feeds.get_feed(feed_id)
        if not feed.enabled:
            return FeedSyncResult(
                provider=feed.provider,
                status=FeedSyncStatus.SKIPPED,
                message="Feed is disabled",
            )

        if self._audit:
            self._audit.log(
                tenant_id=tenant_id or feed.tenant_id,
                action=AuditAction.FEED_SYNC_STARTED,
                message=f"Sync started for {feed.provider.value}",
                actor=actor,
                details={"feed_id": str(feed_id)},
            )

        provider = self._providers.get(feed.provider)
        result = provider.sync(
            FeedSyncRequest(
                feed=feed,
                tenant_id=tenant_id or feed.tenant_id,
                full_refresh=full_refresh,
            )
        )

        persisted_cves = 0
        persisted_iocs = 0
        if result.status == FeedSyncStatus.SUCCEEDED:
            if self._intel:
                for cve in result.cves:
                    self._intel.save_cve(cve, actor=actor)
                    persisted_cves += 1
            if self._iocs:
                for ioc in result.iocs:
                    self._iocs.save_ioc(ioc, actor=actor)
                    persisted_iocs += 1

        feed.last_sync_at = utc_now()
        feed.last_sync_status = result.status.value
        feed.last_sync_message = result.message
        if result.cursor:
            feed.cursor = result.cursor
        self._feeds.save_feed(feed, actor=actor)

        if self._audit:
            action = (
                AuditAction.FEED_SYNC_COMPLETED
                if result.status
                in {FeedSyncStatus.SUCCEEDED, FeedSyncStatus.SKIPPED}
                else AuditAction.FEED_SYNC_FAILED
            )
            self._audit.log(
                tenant_id=tenant_id or feed.tenant_id,
                action=action,
                message=result.message,
                actor=actor,
                success=result.status != FeedSyncStatus.FAILED,
                details={
                    "feed_id": str(feed_id),
                    "status": result.status.value,
                    "persisted_cves": persisted_cves,
                    "persisted_iocs": persisted_iocs,
                },
            )
        return result

    def sync_all_enabled(
        self,
        *,
        tenant_id: Optional[UUID] = None,
        actor: Optional[str] = None,
    ) -> List[FeedSyncResult]:
        feeds = self._feeds.list_feeds(
            tenant_id=tenant_id,
            enabled_only=True,
            include_global=True,
        )
        return [
            self.sync_feed(feed.id, tenant_id=tenant_id, actor=actor) for feed in feeds
        ]
