"""Map between Execution Engine domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from execution_engine.domain.enums import AuditAction
from execution_engine.domain.history import ExecutionAuditRecord, ExecutionHistory
from execution_engine.domain.models import ExecutionResult
from execution_engine.persistence.orm import (
    ExecutionAuditORM,
    ExecutionResultORM,
    ExecutionVersionORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def result_to_orm(result: ExecutionResult, *, version: int) -> ExecutionResultORM:
    return ExecutionResultORM(
        id=result.id,
        tenant_id=result.tenant_id,
        plan_id=result.plan_id,
        finding_id=result.finding_id,
        decision_id=result.decision_id,
        approval_id=result.approval_id,
        authorization_id=result.authorization_id,
        simulation_id=result.simulation_id,
        asset_id=result.asset_id,
        status=result.status.value,
        queue_name=result.context.queue_name,
        algorithm_version=result.algorithm_version,
        current_version=version,
        payload=result.model_dump(mode="json"),
        first_started_at=result.first_started_at,
        last_evaluated_at=result.last_evaluated_at,
        created_at=result.created_at,
        updated_at=result.updated_at,
    )


def apply_result_to_orm(
    row: ExecutionResultORM,
    result: ExecutionResult,
    *,
    version: int,
) -> None:
    row.finding_id = result.finding_id
    row.decision_id = result.decision_id
    row.approval_id = result.approval_id
    row.authorization_id = result.authorization_id
    row.simulation_id = result.simulation_id
    row.asset_id = result.asset_id
    row.status = result.status.value
    row.queue_name = result.context.queue_name
    row.algorithm_version = result.algorithm_version
    row.current_version = version
    row.payload = result.model_dump(mode="json")
    row.first_started_at = result.first_started_at
    row.last_evaluated_at = result.last_evaluated_at
    row.updated_at = result.updated_at


def orm_to_result(row: ExecutionResultORM) -> ExecutionResult:
    return ExecutionResult.model_validate(row.payload)


def version_from_orm(row: ExecutionVersionORM) -> ExecutionHistory:
    return ExecutionHistory(
        id=row.id,
        execution_id=row.execution_id,
        tenant_id=row.tenant_id,
        plan_id=row.plan_id,
        version=row.version,
        snapshot=ExecutionResult.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_from_orm(row: ExecutionAuditORM) -> ExecutionAuditRecord:
    return ExecutionAuditRecord(
        id=row.id,
        execution_id=row.execution_id,
        plan_id=row.plan_id,
        finding_id=row.finding_id,
        approval_id=row.approval_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        status=row.status,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_to_orm(record: ExecutionAuditRecord) -> ExecutionAuditORM:
    return ExecutionAuditORM(
        id=record.id,
        execution_id=record.execution_id,
        plan_id=record.plan_id,
        finding_id=record.finding_id,
        approval_id=record.approval_id,
        tenant_id=record.tenant_id,
        action=record.action.value,
        actor=record.actor,
        message=record.message,
        status=record.status,
        details=record.details,
        created_at=record.created_at,
    )
