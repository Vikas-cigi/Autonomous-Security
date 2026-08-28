"""Map between Simulation Engine domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from simulation_engine.domain.enums import AuditAction
from simulation_engine.domain.history import SimulationAuditRecord, SimulationVersionRecord
from simulation_engine.domain.models import SimulationResult
from simulation_engine.persistence.orm import (
    SimulationAuditORM,
    SimulationResultORM,
    SimulationVersionORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def result_to_orm(result: SimulationResult, *, version: int) -> SimulationResultORM:
    return SimulationResultORM(
        id=result.id,
        tenant_id=result.tenant_id,
        plan_id=result.plan_id,
        finding_id=result.finding_id,
        decision_id=result.decision_id,
        asset_id=result.asset_id,
        outcome=result.outcome.value,
        safe_to_execute=result.safe_to_execute,
        algorithm_version=result.algorithm_version,
        current_version=version,
        payload=result.model_dump(mode="json"),
        simulated_at=result.simulated_at,
        first_simulated_at=result.first_simulated_at,
        last_simulated_at=result.last_simulated_at,
        created_at=result.created_at,
        updated_at=result.updated_at,
    )


def apply_result_to_orm(
    row: SimulationResultORM,
    result: SimulationResult,
    *,
    version: int,
) -> None:
    row.finding_id = result.finding_id
    row.decision_id = result.decision_id
    row.asset_id = result.asset_id
    row.outcome = result.outcome.value
    row.safe_to_execute = result.safe_to_execute
    row.algorithm_version = result.algorithm_version
    row.current_version = version
    row.payload = result.model_dump(mode="json")
    row.simulated_at = result.simulated_at
    row.first_simulated_at = result.first_simulated_at
    row.last_simulated_at = result.last_simulated_at
    row.updated_at = result.updated_at


def orm_to_result(row: SimulationResultORM) -> SimulationResult:
    return SimulationResult.model_validate(row.payload)


def version_from_orm(row: SimulationVersionORM) -> SimulationVersionRecord:
    return SimulationVersionRecord(
        id=row.id,
        simulation_id=row.simulation_id,
        tenant_id=row.tenant_id,
        plan_id=row.plan_id,
        version=row.version,
        snapshot=SimulationResult.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_from_orm(row: SimulationAuditORM) -> SimulationAuditRecord:
    return SimulationAuditRecord(
        id=row.id,
        simulation_id=row.simulation_id,
        plan_id=row.plan_id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        outcome=row.outcome,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_to_orm(record: SimulationAuditRecord) -> SimulationAuditORM:
    return SimulationAuditORM(
        id=record.id,
        simulation_id=record.simulation_id,
        plan_id=record.plan_id,
        finding_id=record.finding_id,
        tenant_id=record.tenant_id,
        action=record.action.value,
        actor=record.actor,
        message=record.message,
        outcome=record.outcome,
        details=record.details,
        created_at=record.created_at,
    )
