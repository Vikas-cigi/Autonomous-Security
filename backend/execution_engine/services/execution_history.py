"""Execution history query helper."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from execution_engine.domain.history import ExecutionHistory
from execution_engine.interfaces.execution_history_repository import (
    ExecutionHistoryRepository,
)
from execution_engine.interfaces.execution_repository import ExecutionRepository
from execution_engine.query.filters import ExecutionSearchFilter
from execution_engine.query.pagination import Page, PageRequest


class ExecutionHistoryService:
    def __init__(
        self,
        execution_repository: ExecutionRepository,
        history_repository: Optional[ExecutionHistoryRepository] = None,
    ) -> None:
        self._exec = execution_repository
        self._history = history_repository

    def list_versions(
        self, execution_id: UUID, tenant_id: UUID
    ) -> List[ExecutionHistory]:
        if self._history is not None:
            return self._history.list_for_execution(execution_id, tenant_id)
        return self._exec.list_versions(execution_id, tenant_id)

    def search_versions(
        self,
        filters: ExecutionSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[ExecutionHistory]:
        if self._history is None:
            return Page.from_items([], request=page or PageRequest(), total_items=0)
        return self._history.search(filters, page or PageRequest())
