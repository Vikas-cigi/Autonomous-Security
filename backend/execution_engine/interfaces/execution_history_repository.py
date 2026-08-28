"""ExecutionHistoryRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from execution_engine.domain.history import ExecutionHistory
from execution_engine.query.filters import ExecutionSearchFilter
from execution_engine.query.pagination import Page, PageRequest


class ExecutionHistoryRepository(ABC):
    @abstractmethod
    def list_for_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> List[ExecutionHistory]:
        ...

    @abstractmethod
    def search(
        self,
        filters: ExecutionSearchFilter,
        page: PageRequest,
    ) -> Page[ExecutionHistory]:
        ...
