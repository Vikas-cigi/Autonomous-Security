"""PostgreSQL-compatible AuditReportingRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from reporting_analytics.domain.history import ReportingAuditRecord
from reporting_analytics.interfaces.audit_reporting_repository import (
    AuditReportingRepository,
)
from reporting_analytics.persistence.mappers import audit_from_orm, audit_to_orm
from reporting_analytics.persistence.orm import ReportingAuditORM
from reporting_analytics.query.filters import AuditReportingSearchFilter
from reporting_analytics.query.pagination import Page, PageRequest
from reporting_analytics.services.audit_logger import AuditLogger


class PostgresAuditReportingRepository(AuditReportingRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def append(self, record: ReportingAuditRecord) -> ReportingAuditRecord:
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

    def list_for_tenant(self, tenant_id: UUID) -> List[ReportingAuditRecord]:
        stmt = (
            select(ReportingAuditORM)
            .where(ReportingAuditORM.tenant_id == tenant_id)
            .order_by(ReportingAuditORM.created_at.asc())
        )
        return [audit_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self, filters: AuditReportingSearchFilter, page: PageRequest
    ) -> Page[ReportingAuditRecord]:
        stmt = select(ReportingAuditORM).where(
            ReportingAuditORM.tenant_id == filters.tenant_id
        )
        if filters.report_id:
            stmt = stmt.where(ReportingAuditORM.report_id == filters.report_id)
        if filters.dashboard_id:
            stmt = stmt.where(ReportingAuditORM.dashboard_id == filters.dashboard_id)
        if filters.actions:
            stmt = stmt.where(ReportingAuditORM.action.in_(filters.actions))
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ReportingAuditORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [audit_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
