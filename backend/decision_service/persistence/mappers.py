"""Map between Decision Service domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from decision_service.domain.enums import AuditAction
from decision_service.domain.history import DecisionAuditRecord, DecisionVersionRecord
from decision_service.domain.models import DecisionResponse
from decision_service.persistence.orm import (
    DecisionAuditORM,
    DecisionORM,
    DecisionVersionORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def decision_to_orm(response: DecisionResponse, *, version: int) -> DecisionORM:
    return DecisionORM(
        id=response.id,
        tenant_id=response.tenant_id,
        finding_id=response.finding_id,
        asset_id=response.asset_id,
        status=response.status.value,
        decision_type=response.recommendation.decision_type.value,
        confidence=response.decision_object.confidence,
        policy_verdict=response.policy_verdict,
        algorithm_version=response.algorithm_version,
        current_version=version,
        payload=response.model_dump(mode="json"),
        decided_at=response.decided_at,
        first_decided_at=response.first_decided_at,
        last_decided_at=response.last_decided_at,
        created_at=response.created_at,
        updated_at=response.updated_at,
    )


def apply_decision_to_orm(
    row: DecisionORM,
    response: DecisionResponse,
    *,
    version: int,
) -> None:
    row.finding_id = response.finding_id
    row.asset_id = response.asset_id
    row.status = response.status.value
    row.decision_type = response.recommendation.decision_type.value
    row.confidence = response.decision_object.confidence
    row.policy_verdict = response.policy_verdict
    row.algorithm_version = response.algorithm_version
    row.current_version = version
    row.payload = response.model_dump(mode="json")
    row.decided_at = response.decided_at
    row.first_decided_at = response.first_decided_at
    row.last_decided_at = response.last_decided_at
    row.updated_at = response.updated_at


def orm_to_decision(row: DecisionORM) -> DecisionResponse:
    return DecisionResponse.model_validate(row.payload)


def version_from_orm(row: DecisionVersionORM) -> DecisionVersionRecord:
    return DecisionVersionRecord(
        id=row.id,
        decision_id=row.decision_id,
        tenant_id=row.tenant_id,
        finding_id=row.finding_id,
        version=row.version,
        snapshot=DecisionResponse.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_from_orm(row: DecisionAuditORM) -> DecisionAuditRecord:
    return DecisionAuditRecord(
        id=row.id,
        decision_id=row.decision_id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        decision_type=row.decision_type,
        confidence=row.confidence,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_to_orm(record: DecisionAuditRecord) -> DecisionAuditORM:
    return DecisionAuditORM(
        id=record.id,
        decision_id=record.decision_id,
        finding_id=record.finding_id,
        tenant_id=record.tenant_id,
        action=record.action.value,
        actor=record.actor,
        message=record.message,
        decision_type=record.decision_type,
        confidence=record.confidence,
        details=record.details,
        created_at=record.created_at,
    )
