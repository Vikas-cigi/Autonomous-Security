"""KPIRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from reporting_analytics.domain.models import KPI
from reporting_analytics.query.filters import KPISearchFilter
from reporting_analytics.query.pagination import Page, PageRequest


class KPIRepository(ABC):
    @abstractmethod
    def save_many(
        self,
        tenant_id: UUID,
        snapshot_id: UUID,
        kpis: List[KPI],
    ) -> List[KPI]:
        ...

    @abstractmethod
    def list_for_snapshot(
        self, tenant_id: UUID, snapshot_id: UUID
    ) -> List[KPI]:
        ...

    @abstractmethod
    def search(
        self, filters: KPISearchFilter, page: PageRequest
    ) -> Page[KPI]:
        ...
