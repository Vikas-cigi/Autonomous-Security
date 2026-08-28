"""Map between Approval Engine domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from approval_engine.domain.enums import AuditAction
from approval_engine.domain.history import ApprovalAuditRecord, ApprovalHistory
from approval_engine.domain.models import ApprovalPolicy, ApprovalRequest
from approval_engine.persistence.orm import (
    ApprovalAuditORM,
    ApprovalPolicyORM,
    ApprovalRequestORM,
    ApprovalVersionORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def request_to_orm(request: ApprovalRequest, *, version: int) -> ApprovalRequestORM:
    return ApprovalRequestORM(
        id=request.id,
        tenant_id=request.tenant_id,
        plan_id=request.plan_id,
        finding_id=request.finding_id,
        decision_id=request.decision_id,
        simulation_id=request.simulation_id,
        asset_id=request.asset_id,
        state=request.state.value,
        emergency=request.emergency,
        algorithm_version=request.algorithm_version,
        current_version=version,
        payload=request.model_dump(mode="json"),
        requested_at=request.requested_at,
        first_requested_at=request.first_requested_at,
        last_evaluated_at=request.last_evaluated_at,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def apply_request_to_orm(
    row: ApprovalRequestORM,
    request: ApprovalRequest,
    *,
    version: int,
) -> None:
    row.finding_id = request.finding_id
    row.decision_id = request.decision_id
    row.simulation_id = request.simulation_id
    row.asset_id = request.asset_id
    row.state = request.state.value
    row.emergency = request.emergency
    row.algorithm_version = request.algorithm_version
    row.current_version = version
    row.payload = request.model_dump(mode="json")
    row.requested_at = request.requested_at
    row.first_requested_at = request.first_requested_at
    row.last_evaluated_at = request.last_evaluated_at
    row.updated_at = request.updated_at


def orm_to_request(row: ApprovalRequestORM) -> ApprovalRequest:
    return ApprovalRequest.model_validate(row.payload)


def version_from_orm(row: ApprovalVersionORM) -> ApprovalHistory:
    return ApprovalHistory(
        id=row.id,
        approval_id=row.approval_id,
        tenant_id=row.tenant_id,
        plan_id=row.plan_id,
        version=row.version,
        snapshot=ApprovalRequest.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def policy_to_orm(policy: ApprovalPolicy) -> ApprovalPolicyORM:
    return ApprovalPolicyORM(
        id=policy.id,
        tenant_id=policy.tenant_id,
        name=policy.name,
        version=policy.version,
        enabled=policy.enabled,
        algorithm_version=policy.algorithm_version,
        payload=policy.model_dump(mode="json"),
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def apply_policy_to_orm(row: ApprovalPolicyORM, policy: ApprovalPolicy) -> None:
    row.name = policy.name
    row.version = policy.version
    row.enabled = policy.enabled
    row.algorithm_version = policy.algorithm_version
    row.payload = policy.model_dump(mode="json")
    row.updated_at = policy.updated_at


def orm_to_policy(row: ApprovalPolicyORM) -> ApprovalPolicy:
    return ApprovalPolicy.model_validate(row.payload)


def audit_from_orm(row: ApprovalAuditORM) -> ApprovalAuditRecord:
    return ApprovalAuditRecord(
        id=row.id,
        approval_id=row.approval_id,
        plan_id=row.plan_id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        state=row.state,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_to_orm(record: ApprovalAuditRecord) -> ApprovalAuditORM:
    return ApprovalAuditORM(
        id=record.id,
        approval_id=record.approval_id,
        plan_id=record.plan_id,
        finding_id=record.finding_id,
        tenant_id=record.tenant_id,
        action=record.action.value,
        actor=record.actor,
        message=record.message,
        state=record.state,
        details=record.details,
        created_at=record.created_at,
    )
