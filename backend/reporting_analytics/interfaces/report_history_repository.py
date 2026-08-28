"""ReportHistoryRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from reporting_analytics.domain.history import ReportHistory


class ReportHistoryRepository(ABC):
    @abstractmethod
    def append(self, history: ReportHistory) -> ReportHistory:
        ...

    @abstractmethod
    def list_for_report(
        self, report_id: UUID, tenant_id: UUID
    ) -> List[ReportHistory]:
        ...

    @abstractmethod
    def get_version(
        self, report_id: UUID, tenant_id: UUID, version: int
    ) -> Optional[ReportHistory]:
        ...
