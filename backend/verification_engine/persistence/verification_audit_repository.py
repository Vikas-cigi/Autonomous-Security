"""PostgreSQL-compatible VerificationAuditRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from verification_engine.domain.history import VerificationAuditRecord
from verification_engine.interfaces.verification_audit_repository import (
    VerificationAuditRepository,
)
from verification_engine.persistence.mappers import audit_from_orm, audit_to_orm
from verification_engine.persistence.orm import VerificationAuditORM
from verification_engine.query.filters import VerificationAuditSearchFilter
from verification_engine.query.pagination import Page, PageRequest
from verification_engine.services.audit_logger import AuditLogger


class PostgresVerificationAuditRepository(VerificationAuditRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def append(self, record: VerificationAuditRecord) -> VerificationAuditRecord:
        row = audit_to_orm(record)
        self._session.add(row)
        self._session.flush()
        self._audit.log(
            tenant_id=record.tenant_id,
            action=record.action,
            message=record.message,
            actor=record.actor,
            details=record.details,
        )
        return audit_from_orm(row)

    def list_for_verification(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationAuditRecord]:
        stmt = (
            select(VerificationAuditORM)
            .where(
                VerificationAuditORM.verification_id == verification_id,
                VerificationAuditORM.tenant_id == tenant_id,
            )
            .order_by(VerificationAuditORM.created_at.asc())
        )
        return [audit_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: VerificationAuditSearchFilter,
        page: PageRequest,
    ) -> Page[VerificationAuditRecord]:
        stmt = select(VerificationAuditORM).where(
            VerificationAuditORM.tenant_id == filters.tenant_id
        )
        if filters.verification_id:
            stmt = stmt.where(
                VerificationAuditORM.verification_id == filters.verification_id
            )
        if filters.execution_id:
            stmt = stmt.where(
                VerificationAuditORM.execution_id == filters.execution_id
            )
        if filters.finding_id:
            stmt = stmt.where(VerificationAuditORM.finding_id == filters.finding_id)
        if filters.actions:
            stmt = stmt.where(VerificationAuditORM.action.in_(filters.actions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(VerificationAuditORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [audit_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
