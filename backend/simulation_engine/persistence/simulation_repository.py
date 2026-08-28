"""PostgreSQL-compatible SimulationRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.common import utc_now
from simulation_engine.domain.enums import AuditAction
from simulation_engine.domain.history import SimulationVersionRecord
from simulation_engine.domain.models import SimulationResult
from simulation_engine.exceptions import SimulationNotFoundError
from simulation_engine.interfaces.simulation_repository import SimulationRepository
from simulation_engine.persistence.mappers import (
    apply_result_to_orm,
    orm_to_result,
    result_to_orm,
    version_from_orm,
)
from simulation_engine.persistence.orm import (
    SimulationAuditORM,
    SimulationResultORM,
    SimulationVersionORM,
)
from simulation_engine.query.filters import SimulationSearchFilter
from simulation_engine.query.pagination import Page, PageRequest
from simulation_engine.services.audit import AuditLogger


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresSimulationRepository(SimulationRepository):
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
        result: SimulationResult,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Simulation result persisted",
    ) -> SimulationResult:
        row = self._session.get(SimulationResultORM, result.id)
        created = row is None

        if created:
            existing = self._session.scalars(
                select(SimulationResultORM).where(
                    SimulationResultORM.tenant_id == result.tenant_id,
                    SimulationResultORM.plan_id == result.plan_id,
                )
            ).first()
            if existing is not None:
                row = existing
                result.id = existing.id
                result.first_simulated_at = _ensure_aware(existing.first_simulated_at)
                created = False

        if created:
            version = 1
            result.current_version = version
            result.touch()
            result.last_simulated_at = utc_now()
            row = result_to_orm(result, version=version)
            self._session.add(row)
            action = AuditAction.RESULT_SAVED
        else:
            if row is None or row.tenant_id != result.tenant_id:
                raise SimulationNotFoundError(result.id, result.tenant_id)
            version = int(row.current_version) + 1
            result.current_version = version
            result.first_simulated_at = _ensure_aware(row.first_simulated_at)
            result.touch()
            result.last_simulated_at = utc_now()
            apply_result_to_orm(row, result, version=version)
            action = AuditAction.RESULT_SAVED

        self._session.flush()
        self._session.add(
            SimulationVersionORM(
                id=uuid4(),
                simulation_id=result.id,
                tenant_id=result.tenant_id,
                plan_id=result.plan_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=result.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.add(
            SimulationAuditORM(
                id=uuid4(),
                simulation_id=result.id,
                plan_id=result.plan_id,
                finding_id=result.finding_id,
                tenant_id=result.tenant_id,
                action=action.value,
                actor=actor,
                message=change_summary,
                outcome=result.outcome.value,
                details={
                    "version": version,
                    "safe_to_execute": result.safe_to_execute,
                    "confidence_score": result.confidence_score,
                },
                created_at=utc_now(),
            )
        )
        self._audit.log(
            tenant_id=result.tenant_id,
            action=action,
            message=change_summary,
            actor=actor,
            details={
                "simulation_id": str(result.id),
                "plan_id": str(result.plan_id),
                "version": version,
                "outcome": result.outcome.value,
            },
        )
        self._session.flush()
        return orm_to_result(row)

    def get(self, simulation_id: UUID, tenant_id: UUID) -> SimulationResult:
        return orm_to_result(self._require(simulation_id, tenant_id))

    def find_by_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> Optional[SimulationResult]:
        stmt = select(SimulationResultORM).where(
            SimulationResultORM.tenant_id == tenant_id,
            SimulationResultORM.plan_id == plan_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_result(row) if row else None

    def search(
        self,
        filters: SimulationSearchFilter,
        page: PageRequest,
    ) -> Page[SimulationResult]:
        stmt = select(SimulationResultORM).where(
            SimulationResultORM.tenant_id == filters.tenant_id
        )
        if filters.plan_id:
            stmt = stmt.where(SimulationResultORM.plan_id == filters.plan_id)
        if filters.finding_id:
            stmt = stmt.where(SimulationResultORM.finding_id == filters.finding_id)
        if filters.decision_id:
            stmt = stmt.where(SimulationResultORM.decision_id == filters.decision_id)
        if filters.outcomes:
            stmt = stmt.where(
                SimulationResultORM.outcome.in_([o.value for o in filters.outcomes])
            )
        if filters.safe_to_execute is not None:
            stmt = stmt.where(
                SimulationResultORM.safe_to_execute == filters.safe_to_execute
            )
        if filters.algorithm_version:
            stmt = stmt.where(
                SimulationResultORM.algorithm_version == filters.algorithm_version
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(SimulationResultORM.last_simulated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_result(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Simulation search",
            details={"total": total},
        )
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(
        self, simulation_id: UUID, tenant_id: UUID
    ) -> List[SimulationVersionRecord]:
        self._require(simulation_id, tenant_id)
        stmt = (
            select(SimulationVersionORM)
            .where(
                SimulationVersionORM.simulation_id == simulation_id,
                SimulationVersionORM.tenant_id == tenant_id,
            )
            .order_by(SimulationVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def _require(self, simulation_id: UUID, tenant_id: UUID) -> SimulationResultORM:
        row = self._session.get(SimulationResultORM, simulation_id)
        if row is None or row.tenant_id != tenant_id:
            raise SimulationNotFoundError(simulation_id, tenant_id)
        return row
