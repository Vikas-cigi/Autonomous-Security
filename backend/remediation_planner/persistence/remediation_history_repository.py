"""PostgreSQL-compatible RemediationHistoryRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from remediation_planner.domain.enums import AuditAction
from remediation_planner.domain.history import RemediationAuditRecord
from remediation_planner.interfaces.remediation_history_repository import (
    RemediationHistoryRepository,
)
from remediation_planner.persistence.mappers import history_from_orm, history_to_orm
from remediation_planner.persistence.orm import RemediationHistoryORM
from remediation_planner.query.filters import RemediationHistorySearchFilter
from remediation_planner.query.pagination import Page, PageRequest
from remediation_planner.services.audit import AuditLogger


class PostgresRemediationHistoryRepository(RemediationHistoryRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def append(self, record: RemediationAuditRecord) -> RemediationAuditRecord:
        row = history_to_orm(record)
        self._session.add(row)
        self._session.flush()
        self._audit.log(
            tenant_id=record.tenant_id,
            action=AuditAction.HISTORY_RECORDED,
            message=record.message,
            actor=record.actor,
            details={
                "plan_id": str(record.plan_id) if record.plan_id else None,
                "action": record.action.value,
            },
        )
        return history_from_orm(row)

    def list_for_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> List[RemediationAuditRecord]:
        stmt = (
            select(RemediationHistoryORM)
            .where(
                RemediationHistoryORM.plan_id == plan_id,
                RemediationHistoryORM.tenant_id == tenant_id,
            )
            .order_by(RemediationHistoryORM.created_at.asc())
        )
        return [history_from_orm(r) for r in self._session.scalars(stmt).all()]

    def list_for_finding(
        self, finding_id: UUID, tenant_id: UUID
    ) -> List[RemediationAuditRecord]:
        stmt = (
            select(RemediationHistoryORM)
            .where(
                RemediationHistoryORM.finding_id == finding_id,
                RemediationHistoryORM.tenant_id == tenant_id,
            )
            .order_by(RemediationHistoryORM.created_at.asc())
        )
        return [history_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: RemediationHistorySearchFilter,
        page: PageRequest,
    ) -> Page[RemediationAuditRecord]:
        stmt = select(RemediationHistoryORM).where(
            RemediationHistoryORM.tenant_id == filters.tenant_id
        )
        if filters.plan_id:
            stmt = stmt.where(RemediationHistoryORM.plan_id == filters.plan_id)
        if filters.finding_id:
            stmt = stmt.where(RemediationHistoryORM.finding_id == filters.finding_id)
        if filters.actions:
            stmt = stmt.where(RemediationHistoryORM.action.in_(filters.actions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(RemediationHistoryORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [history_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
