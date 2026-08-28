"""PostgreSQL-compatible ThreatFeedRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from threat_intelligence.domain.enums import ThreatFeedProviderId
from threat_intelligence.domain.models import ThreatFeedMetadata
from threat_intelligence.exceptions import ThreatFeedNotFoundError
from threat_intelligence.interfaces.threat_feed_repository import ThreatFeedRepository
from threat_intelligence.persistence.mappers import (
    apply_feed_to_orm,
    feed_to_orm,
    orm_to_feed,
)
from threat_intelligence.persistence.orm import ThreatFeedORM


class PostgresThreatFeedRepository(ThreatFeedRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_feed(
        self,
        feed: ThreatFeedMetadata,
        *,
        actor: Optional[str] = None,
    ) -> ThreatFeedMetadata:
        del actor  # reserved for future audit wiring
        row = self._session.get(ThreatFeedORM, feed.id)
        if row is None:
            version = 1
            feed.current_version = version
            feed.touch()
            row = feed_to_orm(feed, version=version)
            self._session.add(row)
        else:
            version = int(row.current_version) + 1
            feed.current_version = version
            feed.touch()
            apply_feed_to_orm(row, feed, version=version)
        self._session.flush()
        return orm_to_feed(row)

    def get_feed(self, feed_id: UUID) -> ThreatFeedMetadata:
        row = self._session.get(ThreatFeedORM, feed_id)
        if row is None:
            raise ThreatFeedNotFoundError(feed_id)
        return orm_to_feed(row)

    def list_feeds(
        self,
        *,
        tenant_id: Optional[UUID] = None,
        provider: Optional[ThreatFeedProviderId] = None,
        enabled_only: bool = False,
        include_global: bool = True,
    ) -> List[ThreatFeedMetadata]:
        stmt = select(ThreatFeedORM)
        if tenant_id is not None:
            if include_global:
                stmt = stmt.where(
                    or_(
                        ThreatFeedORM.tenant_id == tenant_id,
                        ThreatFeedORM.tenant_id.is_(None),
                    )
                )
            else:
                stmt = stmt.where(ThreatFeedORM.tenant_id == tenant_id)
        if provider is not None:
            stmt = stmt.where(ThreatFeedORM.provider == provider.value)
        if enabled_only:
            stmt = stmt.where(ThreatFeedORM.enabled.is_(True))
        stmt = stmt.order_by(ThreatFeedORM.name.asc())
        return [orm_to_feed(r) for r in self._session.scalars(stmt).all()]

    def find_by_provider(
        self,
        provider: ThreatFeedProviderId,
        *,
        tenant_id: Optional[UUID] = None,
    ) -> Optional[ThreatFeedMetadata]:
        stmt = select(ThreatFeedORM).where(ThreatFeedORM.provider == provider.value)
        if tenant_id is not None:
            stmt = stmt.where(
                or_(
                    ThreatFeedORM.tenant_id == tenant_id,
                    ThreatFeedORM.tenant_id.is_(None),
                )
            )
        else:
            stmt = stmt.where(ThreatFeedORM.tenant_id.is_(None))
        row = self._session.scalars(stmt).first()
        return orm_to_feed(row) if row else None
