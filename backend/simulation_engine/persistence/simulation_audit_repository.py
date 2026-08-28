"""PostgreSQL-compatible SimulationAuditRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from simulation_engine.domain.enums import AuditAction
from simulation_engine.domain.history import SimulationAuditRecord
from simulation_engine.interfaces.simulation_audit_repository import (
    SimulationAuditRepository,
)
from simulation_engine.persistence.mappers import audit_from_orm, audit_to_orm
from simulation_engine.persistence.orm import SimulationAuditORM
from simulation_engine.query.filters import SimulationAuditSearchFilter
from simulation_engine.query.pagination import Page, PageRequest
from simulation_engine.services.audit import AuditLogger


class PostgresSimulationAuditRepository(SimulationAuditRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def append(self, record: SimulationAuditRecord) -> SimulationAuditRecord:
        row = audit_to_orm(record)
        self._session.add(row)
        self._session.flush()
        self._audit.log(
            tenant_id=record.tenant_id,
            action=AuditAction.HISTORY_RECORDED,
            message=record.message,
            actor=record.actor,
            details={
                "simulation_id": str(record.simulation_id)
                if record.simulation_id
                else None,
                "action": record.action.value,
            },
        )
        return audit_from_orm(row)

    def list_for_simulation(
        self, simulation_id: UUID, tenant_id: UUID
    ) -> List[SimulationAuditRecord]:
        stmt = (
            select(SimulationAuditORM)
            .where(
                SimulationAuditORM.simulation_id == simulation_id,
                SimulationAuditORM.tenant_id == tenant_id,
            )
            .order_by(SimulationAuditORM.created_at.asc())
        )
        return [audit_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: SimulationAuditSearchFilter,
        page: PageRequest,
    ) -> Page[SimulationAuditRecord]:
        stmt = select(SimulationAuditORM).where(
            SimulationAuditORM.tenant_id == filters.tenant_id
        )
        if filters.simulation_id:
            stmt = stmt.where(
                SimulationAuditORM.simulation_id == filters.simulation_id
            )
        if filters.plan_id:
            stmt = stmt.where(SimulationAuditORM.plan_id == filters.plan_id)
        if filters.actions:
            stmt = stmt.where(SimulationAuditORM.action.in_(filters.actions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(SimulationAuditORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [audit_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
