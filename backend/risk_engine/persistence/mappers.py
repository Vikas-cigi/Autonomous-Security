"""Map between Risk Engine domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from risk_engine.domain.enums import AuditAction
from risk_engine.domain.history import RiskAuditRecord, RiskHistory
from risk_engine.domain.models import RiskAssessment
from risk_engine.persistence.orm import (
    RiskAssessmentORM,
    RiskAssessmentVersionORM,
    RiskHistoryORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def assessment_to_orm(
    assessment: RiskAssessment,
    *,
    version: int,
) -> RiskAssessmentORM:
    return RiskAssessmentORM(
        id=assessment.id,
        tenant_id=assessment.tenant_id,
        finding_id=assessment.finding_id,
        asset_id=assessment.asset_id,
        score_value=assessment.enterprise_risk_score.value,
        risk_level=assessment.risk_level.value,
        priority=assessment.priority.value,
        recommended_sla=assessment.recommended_sla.value,
        trust_score_used=assessment.trust_score_used,
        algorithm_version=assessment.algorithm_version,
        current_version=version,
        payload=assessment.model_dump(mode="json"),
        scored_at=assessment.scored_at,
        first_scored_at=assessment.first_scored_at,
        last_scored_at=assessment.last_scored_at,
        created_at=assessment.created_at,
        updated_at=assessment.updated_at,
    )


def apply_assessment_to_orm(
    row: RiskAssessmentORM,
    assessment: RiskAssessment,
    *,
    version: int,
) -> None:
    row.finding_id = assessment.finding_id
    row.asset_id = assessment.asset_id
    row.score_value = assessment.enterprise_risk_score.value
    row.risk_level = assessment.risk_level.value
    row.priority = assessment.priority.value
    row.recommended_sla = assessment.recommended_sla.value
    row.trust_score_used = assessment.trust_score_used
    row.algorithm_version = assessment.algorithm_version
    row.current_version = version
    row.payload = assessment.model_dump(mode="json")
    row.scored_at = assessment.scored_at
    row.first_scored_at = assessment.first_scored_at
    row.last_scored_at = assessment.last_scored_at
    row.updated_at = assessment.updated_at


def orm_to_assessment(row: RiskAssessmentORM) -> RiskAssessment:
    return RiskAssessment.model_validate(row.payload)


def version_from_orm(row: RiskAssessmentVersionORM) -> RiskHistory:
    return RiskHistory(
        id=row.id,
        assessment_id=row.assessment_id,
        tenant_id=row.tenant_id,
        finding_id=row.finding_id,
        version=row.version,
        snapshot=RiskAssessment.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        risk_score_value=row.risk_score_value,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def history_from_orm(row: RiskHistoryORM) -> RiskAuditRecord:
    return RiskAuditRecord(
        id=row.id,
        assessment_id=row.assessment_id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        risk_score_value=row.risk_score_value,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def history_to_orm(record: RiskAuditRecord) -> RiskHistoryORM:
    return RiskHistoryORM(
        id=record.id,
        assessment_id=record.assessment_id,
        finding_id=record.finding_id,
        tenant_id=record.tenant_id,
        action=record.action.value,
        actor=record.actor,
        message=record.message,
        risk_score_value=record.risk_score_value,
        details=record.details,
        created_at=record.created_at,
    )
