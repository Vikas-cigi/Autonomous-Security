"""DecisionAuditRepository port — append-only audit history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from decision_service.domain.history import DecisionAuditRecord
from decision_service.query.filters import DecisionAuditSearchFilter
from decision_service.query.pagination import Page, PageRequest


class DecisionAuditRepository(ABC):
    """Append-only history for decision orchestration."""

    @abstractmethod
    def append(self, record: DecisionAuditRecord) -> DecisionAuditRecord:
        ...

    @abstractmethod
    def list_for_decision(
        self,
        decision_id: UUID,
        tenant_id: UUID,
    ) -> List[DecisionAuditRecord]:
        ...

    @abstractmethod
    def list_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[DecisionAuditRecord]:
        ...

    @abstractmethod
    def search(
        self,
        filters: DecisionAuditSearchFilter,
        page: PageRequest,
    ) -> Page[DecisionAuditRecord]:
        ...
