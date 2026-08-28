"""DashboardRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from reporting_analytics.domain.enums import DashboardType
from reporting_analytics.domain.models import Dashboard
from reporting_analytics.query.filters import DashboardSearchFilter
from reporting_analytics.query.pagination import Page, PageRequest


class DashboardRepository(ABC):
    @abstractmethod
    def save(self, dashboard: Dashboard, *, actor: Optional[str] = None) -> Dashboard:
        ...

    @abstractmethod
    def get(self, dashboard_id: UUID, tenant_id: UUID) -> Dashboard:
        ...

    @abstractmethod
    def find_latest(
        self, tenant_id: UUID, dashboard_type: DashboardType
    ) -> Optional[Dashboard]:
        ...

    @abstractmethod
    def search(
        self, filters: DashboardSearchFilter, page: PageRequest
    ) -> Page[Dashboard]:
        ...
