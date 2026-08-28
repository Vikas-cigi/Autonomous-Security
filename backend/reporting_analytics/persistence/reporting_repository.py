"""PostgreSQL-compatible ReportingRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.common import utc_now
from reporting_analytics.domain.enums import AuditAction
from reporting_analytics.domain.history import ReportHistory
from reporting_analytics.domain.models import Report
from reporting_analytics.exceptions import ReportNotFoundError
from reporting_analytics.interfaces.reporting_repository import ReportingRepository
from reporting_analytics.persistence.mappers import (
    apply_report_to_orm,
    orm_to_report,
    report_to_orm,
    version_from_orm,
)
from reporting_analytics.persistence.orm import ReportORM, ReportVersionORM
from reporting_analytics.query.filters import ReportSearchFilter
from reporting_analytics.query.pagination import Page, PageRequest
from reporting_analytics.services.audit_logger import AuditLogger


class PostgresReportingRepository(ReportingRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def save(
        self,
        report: Report,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Report persisted",
    ) -> Report:
        row = self._session.get(ReportORM, report.id)
        created = row is None
        if created:
            version = 1
            report.current_version = version
            report.touch()
            row = report_to_orm(report, version=version)
            self._session.add(row)
            action = AuditAction.REPORT_GENERATED
        else:
            if row.tenant_id != report.tenant_id:
                raise ReportNotFoundError(report.id, report.tenant_id)
            version = int(row.current_version) + 1
            report.current_version = version
            report.touch()
            apply_report_to_orm(row, report, version=version)
            action = (
                AuditAction.REPORT_FAILED
                if report.status.value == "failed"
                else AuditAction.REPORT_GENERATED
            )

        self._session.flush()
        self._session.add(
            ReportVersionORM(
                id=uuid4(),
                report_id=report.id,
                tenant_id=report.tenant_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=report.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._audit.log(
            tenant_id=report.tenant_id,
            action=action,
            message=change_summary,
            actor=actor,
            details={
                "report_id": str(report.id),
                "version": version,
                "status": report.status.value,
            },
            success=report.status.value != "failed",
        )
        self._session.flush()
        return orm_to_report(row)

    def get(self, report_id: UUID, tenant_id: UUID) -> Report:
        return orm_to_report(self._require(report_id, tenant_id))

    def search(
        self, filters: ReportSearchFilter, page: PageRequest
    ) -> Page[Report]:
        stmt = select(ReportORM).where(ReportORM.tenant_id == filters.tenant_id)
        if filters.report_types:
            stmt = stmt.where(
                ReportORM.report_type.in_([t.value for t in filters.report_types])
            )
        if filters.statuses:
            stmt = stmt.where(
                ReportORM.status.in_([s.value for s in filters.statuses])
            )
        if filters.algorithm_version:
            stmt = stmt.where(
                ReportORM.algorithm_version == filters.algorithm_version
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ReportORM.updated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_report(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Report search",
            details={"total": total},
        )
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(self, report_id: UUID, tenant_id: UUID) -> List[ReportHistory]:
        self._require(report_id, tenant_id)
        stmt = (
            select(ReportVersionORM)
            .where(
                ReportVersionORM.report_id == report_id,
                ReportVersionORM.tenant_id == tenant_id,
            )
            .order_by(ReportVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def _require(self, report_id: UUID, tenant_id: UUID) -> ReportORM:
        row = self._session.get(ReportORM, report_id)
        if row is None or row.tenant_id != tenant_id:
            raise ReportNotFoundError(report_id, tenant_id)
        return row
