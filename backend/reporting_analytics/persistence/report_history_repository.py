"""PostgreSQL-compatible ReportHistoryRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from reporting_analytics.domain.history import ReportHistory
from reporting_analytics.interfaces.report_history_repository import (
    ReportHistoryRepository,
)
from reporting_analytics.persistence.mappers import version_from_orm
from reporting_analytics.persistence.orm import ReportVersionORM


class PostgresReportHistoryRepository(ReportHistoryRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, history: ReportHistory) -> ReportHistory:
        row = ReportVersionORM(
            id=history.id,
            report_id=history.report_id,
            tenant_id=history.tenant_id,
            version=history.version,
            change_summary=history.change_summary,
            created_by=history.created_by,
            payload=history.snapshot.model_dump(mode="json"),
            created_at=history.created_at,
        )
        self._session.add(row)
        self._session.flush()
        return version_from_orm(row)

    def list_for_report(
        self, report_id: UUID, tenant_id: UUID
    ) -> List[ReportHistory]:
        stmt = (
            select(ReportVersionORM)
            .where(
                ReportVersionORM.report_id == report_id,
                ReportVersionORM.tenant_id == tenant_id,
            )
            .order_by(ReportVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def get_version(
        self, report_id: UUID, tenant_id: UUID, version: int
    ) -> Optional[ReportHistory]:
        stmt = select(ReportVersionORM).where(
            ReportVersionORM.report_id == report_id,
            ReportVersionORM.tenant_id == tenant_id,
            ReportVersionORM.version == version,
        )
        row = self._session.scalars(stmt).first()
        return version_from_orm(row) if row else None
