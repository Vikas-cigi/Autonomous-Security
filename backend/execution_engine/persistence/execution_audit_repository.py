"""PostgreSQL-compatible ExecutionAuditRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from execution_engine.domain.enums import AuditAction
from execution_engine.domain.history import ExecutionAuditRecord
from execution_engine.interfaces.execution_audit_repository import (
    ExecutionAuditRepository,
)
from execution_engine.persistence.mappers import audit_from_orm, audit_to_orm
from execution_engine.persistence.orm import ExecutionAuditORM
from execution_engine.query.filters import ExecutionAuditSearchFilter
from execution_engine.query.pagination import Page, PageRequest
from execution_engine.services.audit_logger import AuditLogger


class PostgresExecutionAuditRepository(ExecutionAuditRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def append(self, record: ExecutionAuditRecord) -> ExecutionAuditRecord:
        row = audit_to_orm(record)
        self._session.add(row)
        self._session.flush()
        self._audit.log(
            tenant_id=record.tenant_id,
            action=AuditAction.HISTORY_RECORDED,
            message=record.message,
            actor=record.actor,
            details={
                "execution_id": str(record.execution_id)
                if record.execution_id
                else None,
                "action": record.action.value,
            },
        )
        return audit_from_orm(row)

    def list_for_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> List[ExecutionAuditRecord]:
        stmt = (
            select(ExecutionAuditORM)
            .where(
                ExecutionAuditORM.execution_id == execution_id,
                ExecutionAuditORM.tenant_id == tenant_id,
            )
            .order_by(ExecutionAuditORM.created_at.asc())
        )
        return [audit_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: ExecutionAuditSearchFilter,
        page: PageRequest,
    ) -> Page[ExecutionAuditRecord]:
        stmt = select(ExecutionAuditORM).where(
            ExecutionAuditORM.tenant_id == filters.tenant_id
        )
        if filters.execution_id:
            stmt = stmt.where(
                ExecutionAuditORM.execution_id == filters.execution_id
            )
        if filters.plan_id:
            stmt = stmt.where(ExecutionAuditORM.plan_id == filters.plan_id)
        if filters.actions:
            stmt = stmt.where(ExecutionAuditORM.action.in_(filters.actions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ExecutionAuditORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [audit_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
