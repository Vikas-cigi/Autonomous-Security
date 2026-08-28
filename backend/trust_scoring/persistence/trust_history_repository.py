"""PostgreSQL-compatible TrustHistoryRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trust_scoring.domain.enums import AuditAction
from trust_scoring.domain.history import TrustAuditRecord
from trust_scoring.interfaces.trust_history_repository import TrustHistoryRepository
from trust_scoring.persistence.mappers import history_from_orm, history_to_orm
from trust_scoring.persistence.orm import TrustHistoryORM
from trust_scoring.query.filters import TrustHistorySearchFilter
from trust_scoring.query.pagination import Page, PageRequest
from trust_scoring.services.audit import AuditLogger


class PostgresTrustHistoryRepository(TrustHistoryRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def append(self, record: TrustAuditRecord) -> TrustAuditRecord:
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
    ) -> List[TrustAuditRecord]:
        stmt = (
            select(TrustHistoryORM)
            .where(
                TrustHistoryORM.assessment_id == assessment_id,
                TrustHistoryORM.tenant_id == tenant_id,
            )
            .order_by(TrustHistoryORM.created_at.asc())
        )
        return [history_from_orm(r) for r in self._session.scalars(stmt).all()]

    def list_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[TrustAuditRecord]:
        stmt = (
            select(TrustHistoryORM)
            .where(
                TrustHistoryORM.finding_id == finding_id,
                TrustHistoryORM.tenant_id == tenant_id,
            )
            .order_by(TrustHistoryORM.created_at.asc())
        )
        return [history_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: TrustHistorySearchFilter,
        page: PageRequest,
    ) -> Page[TrustAuditRecord]:
        stmt = select(TrustHistoryORM).where(
            TrustHistoryORM.tenant_id == filters.tenant_id
        )
        if filters.assessment_id:
            stmt = stmt.where(TrustHistoryORM.assessment_id == filters.assessment_id)
        if filters.finding_id:
            stmt = stmt.where(TrustHistoryORM.finding_id == filters.finding_id)
        if filters.actions:
            stmt = stmt.where(TrustHistoryORM.action.in_(filters.actions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(TrustHistoryORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [history_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
