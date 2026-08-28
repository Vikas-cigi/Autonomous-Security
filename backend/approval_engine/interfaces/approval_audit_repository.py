"""ApprovalAuditRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from approval_engine.domain.history import ApprovalAuditRecord
from approval_engine.query.filters import ApprovalAuditSearchFilter
from approval_engine.query.pagination import Page, PageRequest


class ApprovalAuditRepository(ABC):
    @abstractmethod
    def append(self, record: ApprovalAuditRecord) -> ApprovalAuditRecord:
        ...

    @abstractmethod
    def list_for_approval(
        self, approval_id: UUID, tenant_id: UUID
    ) -> List[ApprovalAuditRecord]:
        ...

    @abstractmethod
    def search(
        self,
        filters: ApprovalAuditSearchFilter,
        page: PageRequest,
    ) -> Page[ApprovalAuditRecord]:
        ...
