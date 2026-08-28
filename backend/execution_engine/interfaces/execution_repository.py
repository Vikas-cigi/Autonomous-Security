"""ExecutionRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from execution_engine.domain.history import ExecutionHistory
from execution_engine.domain.models import ExecutionResult
from execution_engine.query.filters import ExecutionSearchFilter
from execution_engine.query.pagination import Page, PageRequest


class ExecutionRepository(ABC):
    @abstractmethod
    def save(
        self,
        result: ExecutionResult,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Execution persisted",
    ) -> ExecutionResult:
        ...

    @abstractmethod
    def get(self, execution_id: UUID, tenant_id: UUID) -> ExecutionResult:
        ...

    @abstractmethod
    def find_by_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> Optional[ExecutionResult]:
        ...

    @abstractmethod
    def search(
        self,
        filters: ExecutionSearchFilter,
        page: PageRequest,
    ) -> Page[ExecutionResult]:
        ...

    @abstractmethod
    def list_versions(
        self, execution_id: UUID, tenant_id: UUID
    ) -> List[ExecutionHistory]:
        ...
