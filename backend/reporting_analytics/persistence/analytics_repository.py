"""PostgreSQL-compatible AnalyticsRepository."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from reporting_analytics.domain.enums import AuditAction
from reporting_analytics.domain.models import AnalyticsSnapshot
from reporting_analytics.exceptions import ReportingAnalyticsError
from reporting_analytics.interfaces.analytics_repository import AnalyticsRepository
from reporting_analytics.persistence.mappers import orm_to_snapshot, snapshot_to_orm
from reporting_analytics.persistence.orm import AnalyticsSnapshotORM
from reporting_analytics.query.filters import AnalyticsSearchFilter
from reporting_analytics.query.pagination import Page, PageRequest
from reporting_analytics.services.audit_logger import AuditLogger


class PostgresAnalyticsRepository(AnalyticsRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def save(self, snapshot: AnalyticsSnapshot) -> AnalyticsSnapshot:
        snapshot.touch()
        row = self._session.get(AnalyticsSnapshotORM, snapshot.id)
        if row is None:
            row = snapshot_to_orm(snapshot)
            self._session.add(row)
        else:
            if row.tenant_id != snapshot.tenant_id:
                raise ReportingAnalyticsError(
                    "Snapshot tenant mismatch",
                    details={"snapshot_id": str(snapshot.id)},
                )
            row.label = snapshot.label
            row.payload = snapshot.model_dump(mode="json")
            row.updated_at = snapshot.updated_at
        self._session.flush()
        self._audit.log(
            tenant_id=snapshot.tenant_id,
            action=AuditAction.SNAPSHOT_STORED,
            message="Analytics snapshot stored",
            details={"snapshot_id": str(snapshot.id)},
        )
        return orm_to_snapshot(row)

    def get(self, snapshot_id: UUID, tenant_id: UUID) -> AnalyticsSnapshot:
        row = self._session.get(AnalyticsSnapshotORM, snapshot_id)
        if row is None or row.tenant_id != tenant_id:
            raise ReportingAnalyticsError(
                f"Snapshot {snapshot_id} not found for tenant {tenant_id}",
                details={
                    "snapshot_id": str(snapshot_id),
                    "tenant_id": str(tenant_id),
                },
            )
        return orm_to_snapshot(row)

    def latest(self, tenant_id: UUID) -> Optional[AnalyticsSnapshot]:
        stmt = (
            select(AnalyticsSnapshotORM)
            .where(AnalyticsSnapshotORM.tenant_id == tenant_id)
            .order_by(AnalyticsSnapshotORM.created_at.desc())
        )
        row = self._session.scalars(stmt).first()
        return orm_to_snapshot(row) if row else None

    def search(
        self, filters: AnalyticsSearchFilter, page: PageRequest
    ) -> Page[AnalyticsSnapshot]:
        stmt = select(AnalyticsSnapshotORM).where(
            AnalyticsSnapshotORM.tenant_id == filters.tenant_id
        )
        if filters.label:
            stmt = stmt.where(AnalyticsSnapshotORM.label == filters.label)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(AnalyticsSnapshotORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_snapshot(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
