"""PostgreSQL-compatible AIAuditRepository."""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_harness.domain.models import AIAuditRecord
from ai_harness.interfaces.ai_audit_repository import AIAuditRepository
from ai_harness.persistence.mappers import audit_from_orm, audit_to_orm
from ai_harness.persistence.orm import AIAuditORM
from ai_harness.query.filters import AIAuditSearchFilter
from ai_harness.query.pagination import Page, PageRequest


class PostgresAIAuditRepository(AIAuditRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, record: AIAuditRecord) -> AIAuditRecord:
        row = audit_to_orm(record)
        self._session.add(row)
        self._session.flush()
        return audit_from_orm(row)

    def list_for_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> List[AIAuditRecord]:
        stmt = (
            select(AIAuditORM)
            .where(
                AIAuditORM.execution_id == execution_id,
                AIAuditORM.tenant_id == tenant_id,
            )
            .order_by(AIAuditORM.created_at.asc())
        )
        return [audit_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: AIAuditSearchFilter,
        page: PageRequest,
    ) -> Page[AIAuditRecord]:
        stmt = select(AIAuditORM).where(AIAuditORM.tenant_id == filters.tenant_id)
        if filters.execution_id:
            stmt = stmt.where(AIAuditORM.execution_id == filters.execution_id)
        if filters.request_id:
            stmt = stmt.where(AIAuditORM.request_id == filters.request_id)
        if filters.actions:
            stmt = stmt.where(AIAuditORM.action.in_(filters.actions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(AIAuditORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [audit_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
