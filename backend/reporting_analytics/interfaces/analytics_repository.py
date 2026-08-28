"""AnalyticsRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from reporting_analytics.domain.models import AnalyticsSnapshot
from reporting_analytics.query.filters import AnalyticsSearchFilter
from reporting_analytics.query.pagination import Page, PageRequest


class AnalyticsRepository(ABC):
    @abstractmethod
    def save(self, snapshot: AnalyticsSnapshot) -> AnalyticsSnapshot:
        ...

    @abstractmethod
    def get(self, snapshot_id: UUID, tenant_id: UUID) -> AnalyticsSnapshot:
        ...

    @abstractmethod
    def latest(self, tenant_id: UUID) -> Optional[AnalyticsSnapshot]:
        ...

    @abstractmethod
    def search(
        self, filters: AnalyticsSearchFilter, page: PageRequest
    ) -> Page[AnalyticsSnapshot]:
        ...
