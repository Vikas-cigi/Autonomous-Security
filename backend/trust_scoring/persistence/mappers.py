"""Map between Trust Scoring domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from trust_scoring.domain.enums import AuditAction
from trust_scoring.domain.history import TrustAssessmentVersion, TrustAuditRecord
from trust_scoring.domain.models import ConfidenceFactor, TrustAssessment
from trust_scoring.persistence.orm import (
    ConfidenceFactorORM,
    TrustAssessmentORM,
    TrustAssessmentVersionORM,
    TrustHistoryORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def assessment_to_orm(
    assessment: TrustAssessment,
    *,
    version: int,
) -> TrustAssessmentORM:
    return TrustAssessmentORM(
        id=assessment.id,
        tenant_id=assessment.tenant_id,
        finding_id=assessment.finding_id,
        asset_id=assessment.asset_id,
        score_value=assessment.trust_score.value,
        confidence_level=assessment.confidence_level.value,
        recommendation_confidence=assessment.recommendation_confidence.value,
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
    row: TrustAssessmentORM,
    assessment: TrustAssessment,
    *,
    version: int,
) -> None:
    row.finding_id = assessment.finding_id
    row.asset_id = assessment.asset_id
    row.score_value = assessment.trust_score.value
    row.confidence_level = assessment.confidence_level.value
    row.recommendation_confidence = assessment.recommendation_confidence.value
    row.algorithm_version = assessment.algorithm_version
    row.current_version = version
    row.payload = assessment.model_dump(mode="json")
    row.scored_at = assessment.scored_at
    row.first_scored_at = assessment.first_scored_at
    row.last_scored_at = assessment.last_scored_at
    row.updated_at = assessment.updated_at


def orm_to_assessment(row: TrustAssessmentORM) -> TrustAssessment:
    return TrustAssessment.model_validate(row.payload)


def factor_to_orm(
    factor: ConfidenceFactor,
    *,
    assessment_id,
    tenant_id,
    finding_id,
) -> ConfidenceFactorORM:
    return ConfidenceFactorORM(
        id=factor.id,
        assessment_id=assessment_id,
        tenant_id=tenant_id,
        finding_id=finding_id,
        category=factor.category.value,
        polarity=factor.polarity.value,
        label=factor.label,
        raw_score=factor.raw_score,
        weight=factor.weight,
        weighted_contribution=factor.weighted_contribution,
        payload=factor.model_dump(mode="json"),
    )


def orm_to_factor(row: ConfidenceFactorORM) -> ConfidenceFactor:
    return ConfidenceFactor.model_validate(row.payload)


def version_from_orm(row: TrustAssessmentVersionORM) -> TrustAssessmentVersion:
    return TrustAssessmentVersion(
        id=row.id,
        assessment_id=row.assessment_id,
        tenant_id=row.tenant_id,
        finding_id=row.finding_id,
        version=row.version,
        snapshot=TrustAssessment.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def history_from_orm(row: TrustHistoryORM) -> TrustAuditRecord:
    return TrustAuditRecord(
        id=row.id,
        assessment_id=row.assessment_id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        trust_score_value=row.trust_score_value,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def history_to_orm(record: TrustAuditRecord) -> TrustHistoryORM:
    return TrustHistoryORM(
        id=record.id,
        assessment_id=record.assessment_id,
        finding_id=record.finding_id,
        tenant_id=record.tenant_id,
        action=record.action.value,
        actor=record.actor,
        message=record.message,
        trust_score_value=record.trust_score_value,
        details=record.details,
        created_at=record.created_at,
    )
