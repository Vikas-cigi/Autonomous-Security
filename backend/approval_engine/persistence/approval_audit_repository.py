"""PostgreSQL-compatible ApprovalAuditRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from approval_engine.domain.enums import AuditAction
from approval_engine.domain.history import ApprovalAuditRecord
from approval_engine.interfaces.approval_audit_repository import (
    ApprovalAuditRepository,
)
from approval_engine.persistence.mappers import audit_from_orm, audit_to_orm
from approval_engine.persistence.orm import ApprovalAuditORM
from approval_engine.query.filters import ApprovalAuditSearchFilter
from approval_engine.query.pagination import Page, PageRequest
from approval_engine.services.audit_logger import AuditLogger


class PostgresApprovalAuditRepository(ApprovalAuditRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def append(self, record: ApprovalAuditRecord) -> ApprovalAuditRecord:
        row = audit_to_orm(record)
        self._session.add(row)
        self._session.flush()
        self._audit.log(
            tenant_id=record.tenant_id,
            action=AuditAction.HISTORY_RECORDED,
            message=record.message,
            actor=record.actor,
            details={
                "approval_id": str(record.approval_id) if record.approval_id else None,
                "action": record.action.value,
            },
        )
        return audit_from_orm(row)

    def list_for_approval(
        self, approval_id: UUID, tenant_id: UUID
    ) -> List[ApprovalAuditRecord]:
        stmt = (
            select(ApprovalAuditORM)
            .where(
                ApprovalAuditORM.approval_id == approval_id,
                ApprovalAuditORM.tenant_id == tenant_id,
            )
            .order_by(ApprovalAuditORM.created_at.asc())
        )
        return [audit_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: ApprovalAuditSearchFilter,
        page: PageRequest,
    ) -> Page[ApprovalAuditRecord]:
        stmt = select(ApprovalAuditORM).where(
            ApprovalAuditORM.tenant_id == filters.tenant_id
        )
        if filters.approval_id:
            stmt = stmt.where(ApprovalAuditORM.approval_id == filters.approval_id)
        if filters.plan_id:
            stmt = stmt.where(ApprovalAuditORM.plan_id == filters.plan_id)
        if filters.actions:
            stmt = stmt.where(ApprovalAuditORM.action.in_(filters.actions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ApprovalAuditORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [audit_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
