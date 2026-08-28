"""PostgreSQL-compatible ExecutionHistoryRepository."""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from execution_engine.domain.history import ExecutionHistory
from execution_engine.interfaces.execution_history_repository import (
    ExecutionHistoryRepository,
)
from execution_engine.persistence.mappers import version_from_orm
from execution_engine.persistence.orm import ExecutionVersionORM
from execution_engine.query.filters import ExecutionSearchFilter
from execution_engine.query.pagination import Page, PageRequest


class PostgresExecutionHistoryRepository(ExecutionHistoryRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> List[ExecutionHistory]:
        stmt = (
            select(ExecutionVersionORM)
            .where(
                ExecutionVersionORM.execution_id == execution_id,
                ExecutionVersionORM.tenant_id == tenant_id,
            )
            .order_by(ExecutionVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: ExecutionSearchFilter,
        page: PageRequest,
    ) -> Page[ExecutionHistory]:
        stmt = select(ExecutionVersionORM).where(
            ExecutionVersionORM.tenant_id == filters.tenant_id
        )
        if filters.plan_id:
            stmt = stmt.where(ExecutionVersionORM.plan_id == filters.plan_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ExecutionVersionORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [version_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
