"""PostgreSQL-compatible KPIRepository."""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from reporting_analytics.domain.models import KPI
from reporting_analytics.interfaces.kpi_repository import KPIRepository
from reporting_analytics.persistence.mappers import kpi_to_orm, orm_to_kpi
from reporting_analytics.persistence.orm import KPIRecordORM
from reporting_analytics.query.filters import KPISearchFilter
from reporting_analytics.query.pagination import Page, PageRequest


class PostgresKPIRepository(KPIRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_many(
        self,
        tenant_id: UUID,
        snapshot_id: UUID,
        kpis: List[KPI],
    ) -> List[KPI]:
        self._session.execute(
            delete(KPIRecordORM).where(
                KPIRecordORM.tenant_id == tenant_id,
                KPIRecordORM.snapshot_id == snapshot_id,
            )
        )
        rows = [kpi_to_orm(k, tenant_id=tenant_id, snapshot_id=snapshot_id) for k in kpis]
        self._session.add_all(rows)
        self._session.flush()
        return [orm_to_kpi(r) for r in rows]

    def list_for_snapshot(self, tenant_id: UUID, snapshot_id: UUID) -> List[KPI]:
        stmt = select(KPIRecordORM).where(
            KPIRecordORM.tenant_id == tenant_id,
            KPIRecordORM.snapshot_id == snapshot_id,
        )
        return [orm_to_kpi(r) for r in self._session.scalars(stmt).all()]

    def search(self, filters: KPISearchFilter, page: PageRequest) -> Page[KPI]:
        stmt = select(KPIRecordORM).where(KPIRecordORM.tenant_id == filters.tenant_id)
        if filters.snapshot_id:
            stmt = stmt.where(KPIRecordORM.snapshot_id == filters.snapshot_id)
        if filters.names:
            stmt = stmt.where(KPIRecordORM.name.in_(filters.names))
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = stmt.offset(page.offset).limit(page.limit)
        items = [orm_to_kpi(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
