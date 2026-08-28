"""PostgreSQL-compatible TrustRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.common import utc_now
from trust_scoring.domain.enums import AuditAction
from trust_scoring.domain.history import TrustAssessmentVersion
from trust_scoring.domain.models import TrustAssessment
from trust_scoring.exceptions import TrustAssessmentNotFoundError
from trust_scoring.interfaces.trust_repository import TrustRepository
from trust_scoring.persistence.mappers import (
    apply_assessment_to_orm,
    assessment_to_orm,
    orm_to_assessment,
    version_from_orm,
)
from trust_scoring.persistence.orm import (
    TrustAssessmentORM,
    TrustAssessmentVersionORM,
    TrustHistoryORM,
)
from trust_scoring.query.filters import TrustAssessmentSearchFilter
from trust_scoring.query.pagination import Page, PageRequest
from trust_scoring.services.audit import AuditLogger


def _ensure_aware(value: datetime) -> datetime:
    """SQLite may return naive datetimes from server defaults."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresTrustRepository(TrustRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def save_assessment(
        self,
        assessment: TrustAssessment,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Trust assessment persisted",
    ) -> TrustAssessment:
        row = self._session.get(TrustAssessmentORM, assessment.id)
        created = row is None

        # Upsert by finding_id within tenant when id is new but finding already scored.
        if created:
            existing = self._session.scalars(
                select(TrustAssessmentORM).where(
                    TrustAssessmentORM.tenant_id == assessment.tenant_id,
                    TrustAssessmentORM.finding_id == assessment.finding_id,
                )
            ).first()
            if existing is not None:
                row = existing
                assessment.id = existing.id
                assessment.first_scored_at = _ensure_aware(existing.first_scored_at)
                created = False

        if created:
            version = 1
            assessment.current_version = version
            assessment.touch()
            assessment.last_scored_at = utc_now()
            row = assessment_to_orm(assessment, version=version)
            self._session.add(row)
            action = AuditAction.ASSESSMENT_CREATED
        else:
            if row is None or row.tenant_id != assessment.tenant_id:
                raise TrustAssessmentNotFoundError(assessment.id, assessment.tenant_id)
            version = int(row.current_version) + 1
            assessment.current_version = version
            assessment.first_scored_at = _ensure_aware(row.first_scored_at)
            assessment.touch()
            assessment.last_scored_at = utc_now()
            apply_assessment_to_orm(row, assessment, version=version)
            action = AuditAction.ASSESSMENT_UPDATED

        self._session.flush()
        self._session.add(
            TrustAssessmentVersionORM(
                id=uuid4(),
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                finding_id=assessment.finding_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=assessment.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.add(
            TrustHistoryORM(
                id=uuid4(),
                assessment_id=assessment.id,
                finding_id=assessment.finding_id,
                tenant_id=assessment.tenant_id,
                action=action.value,
                actor=actor,
                message=change_summary,
                trust_score_value=assessment.trust_score.value,
                details={
                    "version": version,
                    "confidence_level": assessment.confidence_level.value,
                },
                created_at=utc_now(),
            )
        )
        self._audit.log(
            tenant_id=assessment.tenant_id,
            action=action,
            message=change_summary,
            actor=actor,
            details={
                "assessment_id": str(assessment.id),
                "finding_id": str(assessment.finding_id),
                "version": version,
                "score": assessment.trust_score.value,
            },
        )
        self._session.flush()
        return orm_to_assessment(row)

    def get_assessment(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> TrustAssessment:
        row = self._require(assessment_id, tenant_id)
        return orm_to_assessment(row)

    def find_by_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[TrustAssessment]:
        stmt = select(TrustAssessmentORM).where(
            TrustAssessmentORM.tenant_id == tenant_id,
            TrustAssessmentORM.finding_id == finding_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_assessment(row) if row else None

    def search_assessments(
        self,
        filters: TrustAssessmentSearchFilter,
        page: PageRequest,
    ) -> Page[TrustAssessment]:
        stmt = select(TrustAssessmentORM).where(
            TrustAssessmentORM.tenant_id == filters.tenant_id
        )
        if filters.finding_id:
            stmt = stmt.where(TrustAssessmentORM.finding_id == filters.finding_id)
        if filters.asset_id:
            stmt = stmt.where(TrustAssessmentORM.asset_id == filters.asset_id)
        if filters.trust_levels:
            stmt = stmt.where(
                TrustAssessmentORM.confidence_level.in_(
                    [level.value for level in filters.trust_levels]
                )
            )
        if filters.recommendation_confidences:
            stmt = stmt.where(
                TrustAssessmentORM.recommendation_confidence.in_(
                    [r.value for r in filters.recommendation_confidences]
                )
            )
        if filters.min_score is not None:
            stmt = stmt.where(TrustAssessmentORM.score_value >= filters.min_score)
        if filters.max_score is not None:
            stmt = stmt.where(TrustAssessmentORM.score_value <= filters.max_score)
        if filters.algorithm_version:
            stmt = stmt.where(
                TrustAssessmentORM.algorithm_version == filters.algorithm_version
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(TrustAssessmentORM.last_scored_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_assessment(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Trust assessment search",
            details={"total": total},
        )
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> List[TrustAssessmentVersion]:
        self._require(assessment_id, tenant_id)
        stmt = (
            select(TrustAssessmentVersionORM)
            .where(
                TrustAssessmentVersionORM.assessment_id == assessment_id,
                TrustAssessmentVersionORM.tenant_id == tenant_id,
            )
            .order_by(TrustAssessmentVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def _require(self, assessment_id: UUID, tenant_id: UUID) -> TrustAssessmentORM:
        row = self._session.get(TrustAssessmentORM, assessment_id)
        if row is None or row.tenant_id != tenant_id:
            raise TrustAssessmentNotFoundError(assessment_id, tenant_id)
        return row
