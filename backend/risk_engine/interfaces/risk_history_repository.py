"""RiskHistoryRepository port — append-only audit history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from risk_engine.domain.history import RiskAuditRecord
from risk_engine.query.filters import RiskHistorySearchFilter
from risk_engine.query.pagination import Page, PageRequest


class RiskHistoryRepository(ABC):
    """Append-only history for risk assessments."""

    @abstractmethod
    def append(self, record: RiskAuditRecord) -> RiskAuditRecord:
        ...

    @abstractmethod
    def list_for_assessment(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> List[RiskAuditRecord]:
        ...

    @abstractmethod
    def list_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[RiskAuditRecord]:
        ...

    @abstractmethod
    def search(
        self,
        filters: RiskHistorySearchFilter,
        page: PageRequest,
    ) -> Page[RiskAuditRecord]:
        ...
