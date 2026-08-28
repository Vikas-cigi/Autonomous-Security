"""PostgreSQL-compatible DecisionAuditRepository."""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from decision_service.domain.history import DecisionAuditRecord
from decision_service.interfaces.decision_audit_repository import DecisionAuditRepository
from decision_service.persistence.mappers import audit_from_orm, audit_to_orm
from decision_service.persistence.orm import DecisionAuditORM
from decision_service.query.filters import DecisionAuditSearchFilter
from decision_service.query.pagination import Page, PageRequest


class PostgresDecisionAuditRepository(DecisionAuditRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, record: DecisionAuditRecord) -> DecisionAuditRecord:
        row = audit_to_orm(record)
        self._session.add(row)
        self._session.flush()
        return audit_from_orm(row)

    def list_for_decision(
        self,
        decision_id: UUID,
        tenant_id: UUID,
    ) -> List[DecisionAuditRecord]:
        stmt = (
            select(DecisionAuditORM)
            .where(
                DecisionAuditORM.decision_id == decision_id,
                DecisionAuditORM.tenant_id == tenant_id,
            )
            .order_by(DecisionAuditORM.created_at.asc())
        )
        return [audit_from_orm(r) for r in self._session.scalars(stmt).all()]

    def list_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[DecisionAuditRecord]:
        stmt = (
            select(DecisionAuditORM)
            .where(
                DecisionAuditORM.finding_id == finding_id,
                DecisionAuditORM.tenant_id == tenant_id,
            )
            .order_by(DecisionAuditORM.created_at.asc())
        )
        return [audit_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: DecisionAuditSearchFilter,
        page: PageRequest,
    ) -> Page[DecisionAuditRecord]:
        stmt = select(DecisionAuditORM).where(
            DecisionAuditORM.tenant_id == filters.tenant_id
        )
        if filters.decision_id:
            stmt = stmt.where(DecisionAuditORM.decision_id == filters.decision_id)
        if filters.finding_id:
            stmt = stmt.where(DecisionAuditORM.finding_id == filters.finding_id)
        if filters.actions:
            stmt = stmt.where(DecisionAuditORM.action.in_(filters.actions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(DecisionAuditORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [audit_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
