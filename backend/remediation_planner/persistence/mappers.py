"""Map between Remediation Planner domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from remediation_planner.domain.enums import AuditAction
from remediation_planner.domain.history import RemediationAuditRecord, RemediationHistory
from remediation_planner.domain.models import RemediationPlan
from remediation_planner.persistence.orm import (
    RemediationHistoryORM,
    RemediationPlanORM,
    RemediationPlanVersionORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def plan_to_orm(plan: RemediationPlan, *, version: int) -> RemediationPlanORM:
    return RemediationPlanORM(
        id=plan.id,
        tenant_id=plan.tenant_id,
        finding_id=plan.finding_id,
        decision_id=plan.decision_id,
        asset_id=plan.asset_id,
        status=plan.status.value,
        execution_type=plan.execution_type.value,
        priority=plan.priority.value,
        algorithm_version=plan.algorithm_version,
        current_version=version,
        payload=plan.model_dump(mode="json"),
        planned_at=plan.planned_at,
        first_planned_at=plan.first_planned_at,
        last_planned_at=plan.last_planned_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def apply_plan_to_orm(
    row: RemediationPlanORM,
    plan: RemediationPlan,
    *,
    version: int,
) -> None:
    row.finding_id = plan.finding_id
    row.decision_id = plan.decision_id
    row.asset_id = plan.asset_id
    row.status = plan.status.value
    row.execution_type = plan.execution_type.value
    row.priority = plan.priority.value
    row.algorithm_version = plan.algorithm_version
    row.current_version = version
    row.payload = plan.model_dump(mode="json")
    row.planned_at = plan.planned_at
    row.first_planned_at = plan.first_planned_at
    row.last_planned_at = plan.last_planned_at
    row.updated_at = plan.updated_at


def orm_to_plan(row: RemediationPlanORM) -> RemediationPlan:
    return RemediationPlan.model_validate(row.payload)


def version_from_orm(row: RemediationPlanVersionORM) -> RemediationHistory:
    return RemediationHistory(
        id=row.id,
        plan_id=row.plan_id,
        tenant_id=row.tenant_id,
        finding_id=row.finding_id,
        version=row.version,
        snapshot=RemediationPlan.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def history_from_orm(row: RemediationHistoryORM) -> RemediationAuditRecord:
    return RemediationAuditRecord(
        id=row.id,
        plan_id=row.plan_id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        execution_type=row.execution_type,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def history_to_orm(record: RemediationAuditRecord) -> RemediationHistoryORM:
    return RemediationHistoryORM(
        id=record.id,
        plan_id=record.plan_id,
        finding_id=record.finding_id,
        tenant_id=record.tenant_id,
        action=record.action.value,
        actor=record.actor,
        message=record.message,
        execution_type=record.execution_type,
        details=record.details,
        created_at=record.created_at,
    )
