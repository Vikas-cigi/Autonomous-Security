"""PostgreSQL-compatible DashboardRepository."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from reporting_analytics.domain.enums import AuditAction, DashboardType
from reporting_analytics.domain.models import Dashboard
from reporting_analytics.exceptions import DashboardNotFoundError
from reporting_analytics.interfaces.dashboard_repository import DashboardRepository
from reporting_analytics.persistence.mappers import (
    apply_dashboard_to_orm,
    dashboard_to_orm,
    orm_to_dashboard,
)
from reporting_analytics.persistence.orm import DashboardORM
from reporting_analytics.query.filters import DashboardSearchFilter
from reporting_analytics.query.pagination import Page, PageRequest
from reporting_analytics.services.audit_logger import AuditLogger


class PostgresDashboardRepository(DashboardRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def save(self, dashboard: Dashboard, *, actor: Optional[str] = None) -> Dashboard:
        row = self._session.get(DashboardORM, dashboard.id)
        if row is None:
            dashboard.touch()
            row = dashboard_to_orm(dashboard)
            self._session.add(row)
        else:
            if row.tenant_id != dashboard.tenant_id:
                raise DashboardNotFoundError(dashboard.id, dashboard.tenant_id)
            dashboard.touch()
            apply_dashboard_to_orm(row, dashboard)
        self._session.flush()
        self._audit.log(
            tenant_id=dashboard.tenant_id,
            action=AuditAction.DASHBOARD_ACCESSED,
            message=f"Dashboard saved: {dashboard.dashboard_type.value}",
            actor=actor,
            details={"dashboard_id": str(dashboard.id)},
        )
        return orm_to_dashboard(row)

    def get(self, dashboard_id: UUID, tenant_id: UUID) -> Dashboard:
        row = self._session.get(DashboardORM, dashboard_id)
        if row is None or row.tenant_id != tenant_id:
            raise DashboardNotFoundError(dashboard_id, tenant_id)
        return orm_to_dashboard(row)

    def find_latest(
        self, tenant_id: UUID, dashboard_type: DashboardType
    ) -> Optional[Dashboard]:
        stmt = (
            select(DashboardORM)
            .where(
                DashboardORM.tenant_id == tenant_id,
                DashboardORM.dashboard_type == dashboard_type.value,
            )
            .order_by(DashboardORM.generated_at.desc())
        )
        row = self._session.scalars(stmt).first()
        return orm_to_dashboard(row) if row else None

    def search(
        self, filters: DashboardSearchFilter, page: PageRequest
    ) -> Page[Dashboard]:
        stmt = select(DashboardORM).where(DashboardORM.tenant_id == filters.tenant_id)
        if filters.dashboard_types:
            stmt = stmt.where(
                DashboardORM.dashboard_type.in_(
                    [t.value for t in filters.dashboard_types]
                )
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(DashboardORM.generated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_dashboard(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
