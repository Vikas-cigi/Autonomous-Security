"""AIExecutionRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from ai_harness.domain.models import AIExecution
from ai_harness.query.filters import AIExecutionSearchFilter
from ai_harness.query.pagination import Page, PageRequest


class AIExecutionRepository(ABC):
    @abstractmethod
    def save(self, execution: AIExecution) -> AIExecution:
        ...

    @abstractmethod
    def get(self, execution_id: UUID, tenant_id: UUID) -> AIExecution:
        ...

    @abstractmethod
    def find_by_request(
        self,
        request_id: UUID,
        tenant_id: UUID,
    ) -> Optional[AIExecution]:
        ...

    @abstractmethod
    def search(
        self,
        filters: AIExecutionSearchFilter,
        page: PageRequest,
    ) -> Page[AIExecution]:
        ...
