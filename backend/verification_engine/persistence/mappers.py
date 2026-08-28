"""Map between Verification Engine domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from verification_engine.domain.enums import AuditAction
from verification_engine.domain.history import VerificationAuditRecord, VerificationHistory
from verification_engine.domain.models import VerificationEvidence, VerificationResult
from verification_engine.persistence.orm import (
    VerificationAuditORM,
    VerificationEvidenceORM,
    VerificationResultORM,
    VerificationVersionORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def result_to_orm(result: VerificationResult, *, version: int) -> VerificationResultORM:
    return VerificationResultORM(
        id=result.id,
        tenant_id=result.tenant_id,
        execution_id=result.execution_id,
        plan_id=result.plan_id,
        finding_id=result.finding_id,
        decision_id=result.decision_id,
        asset_id=result.asset_id,
        status=result.status.value,
        algorithm_version=result.algorithm_version,
        current_version=version,
        payload=result.model_dump(mode="json"),
        first_started_at=result.first_started_at,
        last_evaluated_at=result.last_evaluated_at,
        created_at=result.created_at,
        updated_at=result.updated_at,
    )


def apply_result_to_orm(
    row: VerificationResultORM,
    result: VerificationResult,
    *,
    version: int,
) -> None:
    row.finding_id = result.finding_id
    row.decision_id = result.decision_id
    row.plan_id = result.plan_id
    row.asset_id = result.asset_id
    row.status = result.status.value
    row.algorithm_version = result.algorithm_version
    row.current_version = version
    row.payload = result.model_dump(mode="json")
    row.first_started_at = result.first_started_at
    row.last_evaluated_at = result.last_evaluated_at
    row.updated_at = result.updated_at


def orm_to_result(row: VerificationResultORM) -> VerificationResult:
    return VerificationResult.model_validate(row.payload)


def version_from_orm(row: VerificationVersionORM) -> VerificationHistory:
    return VerificationHistory(
        id=row.id,
        verification_id=row.verification_id,
        tenant_id=row.tenant_id,
        execution_id=row.execution_id,
        version=row.version,
        snapshot=VerificationResult.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_from_orm(row: VerificationAuditORM) -> VerificationAuditRecord:
    return VerificationAuditRecord(
        id=row.id,
        verification_id=row.verification_id,
        execution_id=row.execution_id,
        finding_id=row.finding_id,
        plan_id=row.plan_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        status=row.status,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_to_orm(record: VerificationAuditRecord) -> VerificationAuditORM:
    return VerificationAuditORM(
        id=record.id,
        verification_id=record.verification_id,
        execution_id=record.execution_id,
        finding_id=record.finding_id,
        plan_id=record.plan_id,
        tenant_id=record.tenant_id,
        action=record.action.value,
        actor=record.actor,
        message=record.message,
        status=record.status,
        details=record.details,
        created_at=record.created_at,
    )


def evidence_from_orm(row: VerificationEvidenceORM) -> VerificationEvidence:
    return VerificationEvidence(
        evidence_id=row.evidence_id,
        phase=row.phase,
        kind=row.kind,
        summary=row.summary,
        source=row.source,
        indicates_resolved=row.indicates_resolved,
        attributes={str(k): str(v) for k, v in (row.attributes or {}).items()},
        collected_at=_as_utc(row.collected_at) or row.collected_at,
    )


def evidence_to_orm(
    evidence: VerificationEvidence,
    *,
    verification_id,
    tenant_id,
) -> VerificationEvidenceORM:
    return VerificationEvidenceORM(
        verification_id=verification_id,
        tenant_id=tenant_id,
        evidence_id=evidence.evidence_id,
        phase=evidence.phase,
        kind=evidence.kind,
        summary=evidence.summary,
        source=evidence.source,
        indicates_resolved=evidence.indicates_resolved,
        attributes=dict(evidence.attributes),
        collected_at=evidence.collected_at,
    )
