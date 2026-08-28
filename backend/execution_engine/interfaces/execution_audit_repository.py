"""ExecutionAuditRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from execution_engine.domain.history import ExecutionAuditRecord
from execution_engine.query.filters import ExecutionAuditSearchFilter
from execution_engine.query.pagination import Page, PageRequest


class ExecutionAuditRepository(ABC):
    @abstractmethod
    def append(self, record: ExecutionAuditRecord) -> ExecutionAuditRecord:
        ...

    @abstractmethod
    def list_for_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> List[ExecutionAuditRecord]:
        ...

    @abstractmethod
    def search(
        self,
        filters: ExecutionAuditSearchFilter,
        page: PageRequest,
    ) -> Page[ExecutionAuditRecord]:
        ...
