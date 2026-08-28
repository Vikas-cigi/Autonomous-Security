"""RemediationHistoryRepository port — append-only audit history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from remediation_planner.domain.history import RemediationAuditRecord
from remediation_planner.query.filters import RemediationHistorySearchFilter
from remediation_planner.query.pagination import Page, PageRequest


class RemediationHistoryRepository(ABC):
    @abstractmethod
    def append(self, record: RemediationAuditRecord) -> RemediationAuditRecord:
        ...

    @abstractmethod
    def list_for_plan(
        self,
        plan_id: UUID,
        tenant_id: UUID,
    ) -> List[RemediationAuditRecord]:
        ...

    @abstractmethod
    def list_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[RemediationAuditRecord]:
        ...

    @abstractmethod
    def search(
        self,
        filters: RemediationHistorySearchFilter,
        page: PageRequest,
    ) -> Page[RemediationAuditRecord]:
        ...
