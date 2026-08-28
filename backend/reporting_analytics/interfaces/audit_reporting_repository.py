"""AuditReportingRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from reporting_analytics.domain.history import ReportingAuditRecord
from reporting_analytics.query.filters import AuditReportingSearchFilter
from reporting_analytics.query.pagination import Page, PageRequest


class AuditReportingRepository(ABC):
    @abstractmethod
    def append(self, record: ReportingAuditRecord) -> ReportingAuditRecord:
        ...

    @abstractmethod
    def list_for_tenant(self, tenant_id: UUID) -> List[ReportingAuditRecord]:
        ...

    @abstractmethod
    def search(
        self, filters: AuditReportingSearchFilter, page: PageRequest
    ) -> Page[ReportingAuditRecord]:
        ...
