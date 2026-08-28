"""AIAuditRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from ai_harness.domain.models import AIAuditRecord
from ai_harness.query.filters import AIAuditSearchFilter
from ai_harness.query.pagination import Page, PageRequest


class AIAuditRepository(ABC):
    @abstractmethod
    def append(self, record: AIAuditRecord) -> AIAuditRecord:
        ...

    @abstractmethod
    def list_for_execution(
        self,
        execution_id: UUID,
        tenant_id: UUID,
    ) -> List[AIAuditRecord]:
        ...

    @abstractmethod
    def search(
        self,
        filters: AIAuditSearchFilter,
        page: PageRequest,
    ) -> Page[AIAuditRecord]:
        ...
