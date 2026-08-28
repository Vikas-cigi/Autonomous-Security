"""PostgreSQL-compatible AIExecutionRepository."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_harness.domain.models import AIExecution
from ai_harness.exceptions import AIExecutionNotFoundError
from ai_harness.interfaces.ai_execution_repository import AIExecutionRepository
from ai_harness.persistence.mappers import (
    apply_execution_to_orm,
    execution_to_orm,
    orm_to_execution,
)
from ai_harness.persistence.orm import AIExecutionORM
from ai_harness.query.filters import AIExecutionSearchFilter
from ai_harness.query.pagination import Page, PageRequest


class PostgresAIExecutionRepository(AIExecutionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, execution: AIExecution) -> AIExecution:
        row = self._session.get(AIExecutionORM, execution.id)
        if row is None:
            existing = self._session.scalars(
                select(AIExecutionORM).where(
                    AIExecutionORM.tenant_id == execution.tenant_id,
                    AIExecutionORM.request_id == execution.request_id,
                )
            ).first()
            if existing is not None:
                row = existing
                execution.id = existing.id

        execution.touch()
        if row is None:
            row = execution_to_orm(execution)
            self._session.add(row)
        else:
            if row.tenant_id != execution.tenant_id:
                raise AIExecutionNotFoundError(execution.id, execution.tenant_id)
            apply_execution_to_orm(row, execution)
        self._session.flush()
        return orm_to_execution(row)

    def get(self, execution_id: UUID, tenant_id: UUID) -> AIExecution:
        row = self._session.get(AIExecutionORM, execution_id)
        if row is None or row.tenant_id != tenant_id:
            raise AIExecutionNotFoundError(execution_id, tenant_id)
        return orm_to_execution(row)

    def find_by_request(
        self, request_id: UUID, tenant_id: UUID
    ) -> Optional[AIExecution]:
        stmt = select(AIExecutionORM).where(
            AIExecutionORM.tenant_id == tenant_id,
            AIExecutionORM.request_id == request_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_execution(row) if row else None

    def search(
        self,
        filters: AIExecutionSearchFilter,
        page: PageRequest,
    ) -> Page[AIExecution]:
        stmt = select(AIExecutionORM).where(
            AIExecutionORM.tenant_id == filters.tenant_id
        )
        if filters.request_id:
            stmt = stmt.where(AIExecutionORM.request_id == filters.request_id)
        if filters.correlation_id:
            stmt = stmt.where(AIExecutionORM.correlation_id == filters.correlation_id)
        if filters.statuses:
            stmt = stmt.where(
                AIExecutionORM.status.in_([s.value for s in filters.statuses])
            )
        if filters.provider:
            stmt = stmt.where(AIExecutionORM.selected_provider == filters.provider)
        if filters.algorithm_version:
            stmt = stmt.where(
                AIExecutionORM.algorithm_version == filters.algorithm_version
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(AIExecutionORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_execution(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
