"""Map between canonical Pydantic models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from models.evidence import EvidenceObject
from models.security_finding import SecurityFindingObject
from evidence_repository.domain.enums import AuditAction, LifecycleState, to_lifecycle
from evidence_repository.domain.history import FindingHistory
from evidence_repository.domain.versioning import EvidenceVersion, FindingVersion
from evidence_repository.fingerprint import correlation_key, finding_fingerprint
from evidence_repository.persistence.orm import (
    EvidenceORM,
    EvidenceVersionORM,
    FindingHistoryORM,
    FindingORM,
    FindingVersionORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize DB datetimes to timezone-aware UTC (SQLite returns naive)."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def finding_to_orm(
    finding: SecurityFindingObject,
    *,
    current_version: int,
    correlation_group_id=None,
) -> FindingORM:
    """Create/replace ORM fields from a canonical finding."""

    payload = finding.model_dump(mode="json")
    return FindingORM(
        id=finding.id,
        tenant_id=finding.tenant_id,
        asset_id=finding.asset_id,
        source_tool=finding.source_tool.value,
        finding_type=finding.finding_type.value,
        severity=finding.severity.value,
        status=finding.status.value,
        lifecycle=to_lifecycle(finding.status).value,
        cvss_score=finding.cvss_score,
        confidence_score=finding.confidence_score,
        title=finding.title,
        description=finding.description,
        fingerprint=finding_fingerprint(finding),
        correlation_key=correlation_key(finding),
        correlation_group_id=correlation_group_id,
        current_version=current_version,
        payload=payload,
        created_at=finding.created_at,
        updated_at=finding.updated_at,
    )


def apply_finding_to_orm(
    row: FindingORM,
    finding: SecurityFindingObject,
    *,
    current_version: int,
) -> None:
    """Mutate an existing finding row from a canonical model."""

    row.asset_id = finding.asset_id
    row.source_tool = finding.source_tool.value
    row.finding_type = finding.finding_type.value
    row.severity = finding.severity.value
    row.status = finding.status.value
    row.lifecycle = to_lifecycle(finding.status).value
    row.cvss_score = finding.cvss_score
    row.confidence_score = finding.confidence_score
    row.title = finding.title
    row.description = finding.description
    row.fingerprint = finding_fingerprint(finding)
    row.correlation_key = correlation_key(finding)
    row.current_version = current_version
    row.payload = finding.model_dump(mode="json")
    row.updated_at = finding.updated_at


def orm_to_finding(row: FindingORM) -> SecurityFindingObject:
    """Deserialize canonical finding from ORM payload."""

    return SecurityFindingObject.model_validate(row.payload)


def evidence_to_orm(
    evidence: EvidenceObject,
    *,
    finding_id,
    tenant_id,
    current_version: int,
) -> EvidenceORM:
    """Create evidence ORM row."""

    return EvidenceORM(
        id=evidence.id,
        tenant_id=tenant_id,
        finding_id=finding_id,
        raw_artifact_id=evidence.raw_artifact_id,
        source=evidence.source.value,
        validation_status=evidence.validation_status.value,
        confidence=evidence.confidence,
        content_hash=evidence.hash.value,
        hash_algorithm=evidence.hash.algorithm.value,
        current_version=current_version,
        payload=evidence.model_dump(mode="json"),
        created_at=evidence.timestamp,
        updated_at=evidence.timestamp,
    )


def apply_evidence_to_orm(
    row: EvidenceORM,
    evidence: EvidenceObject,
    *,
    current_version: int,
) -> None:
    """Mutate evidence row from canonical model."""

    row.raw_artifact_id = evidence.raw_artifact_id
    row.source = evidence.source.value
    row.validation_status = evidence.validation_status.value
    row.confidence = evidence.confidence
    row.content_hash = evidence.hash.value
    row.hash_algorithm = evidence.hash.algorithm.value
    row.current_version = current_version
    row.payload = evidence.model_dump(mode="json")
    row.updated_at = evidence.timestamp


def orm_to_evidence(row: EvidenceORM) -> EvidenceObject:
    """Deserialize evidence from ORM payload."""

    return EvidenceObject.model_validate(row.payload)


def finding_version_from_orm(row: FindingVersionORM) -> FindingVersion:
    return FindingVersion(
        id=row.id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        version=row.version,
        snapshot=SecurityFindingObject.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at),
    )


def evidence_version_from_orm(row: EvidenceVersionORM) -> EvidenceVersion:
    return EvidenceVersion(
        id=row.id,
        evidence_id=row.evidence_id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        version=row.version,
        snapshot=EvidenceObject.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at),
    )


def history_from_orm(row: FindingHistoryORM) -> FindingHistory:
    from models.enums import FindingStatus

    return FindingHistory(
        id=row.id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        from_status=FindingStatus(row.from_status) if row.from_status else None,
        to_status=FindingStatus(row.to_status) if row.to_status else None,
        from_lifecycle=LifecycleState(row.from_lifecycle) if row.from_lifecycle else None,
        to_lifecycle=LifecycleState(row.to_lifecycle) if row.to_lifecycle else None,
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        correlation_id=row.correlation_id,
        created_at=_as_utc(row.created_at),
    )
