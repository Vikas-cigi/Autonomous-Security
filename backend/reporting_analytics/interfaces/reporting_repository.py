"""ReportingRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from reporting_analytics.domain.history import ReportHistory
from reporting_analytics.domain.models import Report
from reporting_analytics.query.filters import ReportSearchFilter
from reporting_analytics.query.pagination import Page, PageRequest


class ReportingRepository(ABC):
    @abstractmethod
    def save(
        self,
        report: Report,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Report persisted",
    ) -> Report:
        ...

    @abstractmethod
    def get(self, report_id: UUID, tenant_id: UUID) -> Report:
        ...

    @abstractmethod
    def search(
        self, filters: ReportSearchFilter, page: PageRequest
    ) -> Page[Report]:
        ...

    @abstractmethod
    def list_versions(self, report_id: UUID, tenant_id: UUID) -> List[ReportHistory]:
        ...
