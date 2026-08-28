"""PostgreSQL-compatible RiskHistoryRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from risk_engine.domain.enums import AuditAction
from risk_engine.domain.history import RiskAuditRecord
from risk_engine.interfaces.risk_history_repository import RiskHistoryRepository
from risk_engine.persistence.mappers import history_from_orm, history_to_orm
from risk_engine.persistence.orm import RiskHistoryORM
from risk_engine.query.filters import RiskHistorySearchFilter
from risk_engine.query.pagination import Page, PageRequest
from risk_engine.services.audit import AuditLogger


class PostgresRiskHistoryRepository(RiskHistoryRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def append(self, record: RiskAuditRecord) -> RiskAuditRecord:
        row = history_to_orm(record)
        self._session.add(row)
        self._session.flush()
        self._audit.log(
            tenant_id=record.tenant_id,
            action=AuditAction.HISTORY_RECORDED,
            message=record.message,
            actor=record.actor,
            details={
                "assessment_id": str(record.assessment_id) if record.assessment_id else None,
                "finding_id": str(record.finding_id) if record.finding_id else None,
                "action": record.action.value,
            },
        )
        return history_from_orm(row)

    def list_for_assessment(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> List[RiskAuditRecord]:
        stmt = (
            select(RiskHistoryORM)
            .where(
                RiskHistoryORM.assessment_id == assessment_id,
                RiskHistoryORM.tenant_id == tenant_id,
            )
            .order_by(RiskHistoryORM.created_at.asc())
        )
        return [history_from_orm(r) for r in self._session.scalars(stmt).all()]

    def list_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[RiskAuditRecord]:
        stmt = (
            select(RiskHistoryORM)
            .where(
                RiskHistoryORM.finding_id == finding_id,
                RiskHistoryORM.tenant_id == tenant_id,
            )
            .order_by(RiskHistoryORM.created_at.asc())
        )
        return [history_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: RiskHistorySearchFilter,
        page: PageRequest,
    ) -> Page[RiskAuditRecord]:
        stmt = select(RiskHistoryORM).where(
            RiskHistoryORM.tenant_id == filters.tenant_id
        )
        if filters.assessment_id:
            stmt = stmt.where(RiskHistoryORM.assessment_id == filters.assessment_id)
        if filters.finding_id:
            stmt = stmt.where(RiskHistoryORM.finding_id == filters.finding_id)
        if filters.actions:
            stmt = stmt.where(RiskHistoryORM.action.in_(filters.actions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(RiskHistoryORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [history_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
