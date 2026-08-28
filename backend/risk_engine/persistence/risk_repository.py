"""PostgreSQL-compatible RiskRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.common import utc_now
from risk_engine.domain.enums import AuditAction
from risk_engine.domain.history import RiskHistory
from risk_engine.domain.models import RiskAssessment
from risk_engine.exceptions import RiskAssessmentNotFoundError
from risk_engine.interfaces.risk_repository import RiskRepository
from risk_engine.persistence.mappers import (
    apply_assessment_to_orm,
    assessment_to_orm,
    orm_to_assessment,
    version_from_orm,
)
from risk_engine.persistence.orm import (
    RiskAssessmentORM,
    RiskAssessmentVersionORM,
    RiskHistoryORM,
)
from risk_engine.query.filters import RiskAssessmentSearchFilter
from risk_engine.query.pagination import Page, PageRequest
from risk_engine.services.audit import AuditLogger


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresRiskRepository(RiskRepository):
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
        assessment: RiskAssessment,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Risk assessment persisted",
    ) -> RiskAssessment:
        row = self._session.get(RiskAssessmentORM, assessment.id)
        created = row is None

        if created:
            existing = self._session.scalars(
                select(RiskAssessmentORM).where(
                    RiskAssessmentORM.tenant_id == assessment.tenant_id,
                    RiskAssessmentORM.finding_id == assessment.finding_id,
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
                raise RiskAssessmentNotFoundError(assessment.id, assessment.tenant_id)
            version = int(row.current_version) + 1
            assessment.current_version = version
            assessment.first_scored_at = _ensure_aware(row.first_scored_at)
            assessment.touch()
            assessment.last_scored_at = utc_now()
            apply_assessment_to_orm(row, assessment, version=version)
            action = AuditAction.ASSESSMENT_UPDATED

        self._session.flush()
        self._session.add(
            RiskAssessmentVersionORM(
                id=uuid4(),
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                finding_id=assessment.finding_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                risk_score_value=assessment.enterprise_risk_score.value,
                payload=assessment.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.add(
            RiskHistoryORM(
                id=uuid4(),
                assessment_id=assessment.id,
                finding_id=assessment.finding_id,
                tenant_id=assessment.tenant_id,
                action=action.value,
                actor=actor,
                message=change_summary,
                risk_score_value=assessment.enterprise_risk_score.value,
                details={
                    "version": version,
                    "risk_level": assessment.risk_level.value,
                    "priority": assessment.priority.value,
                    "recommended_sla": assessment.recommended_sla.value,
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
                "score": assessment.enterprise_risk_score.value,
            },
        )
        self._session.flush()
        return orm_to_assessment(row)

    def get_assessment(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> RiskAssessment:
        row = self._require(assessment_id, tenant_id)
        return orm_to_assessment(row)

    def find_by_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[RiskAssessment]:
        stmt = select(RiskAssessmentORM).where(
            RiskAssessmentORM.tenant_id == tenant_id,
            RiskAssessmentORM.finding_id == finding_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_assessment(row) if row else None

    def search_assessments(
        self,
        filters: RiskAssessmentSearchFilter,
        page: PageRequest,
    ) -> Page[RiskAssessment]:
        stmt = select(RiskAssessmentORM).where(
            RiskAssessmentORM.tenant_id == filters.tenant_id
        )
        if filters.finding_id:
            stmt = stmt.where(RiskAssessmentORM.finding_id == filters.finding_id)
        if filters.asset_id:
            stmt = stmt.where(RiskAssessmentORM.asset_id == filters.asset_id)
        if filters.risk_levels:
            stmt = stmt.where(
                RiskAssessmentORM.risk_level.in_(
                    [level.value for level in filters.risk_levels]
                )
            )
        if filters.priorities:
            stmt = stmt.where(
                RiskAssessmentORM.priority.in_([p.value for p in filters.priorities])
            )
        if filters.recommended_slas:
            stmt = stmt.where(
                RiskAssessmentORM.recommended_sla.in_(
                    [s.value for s in filters.recommended_slas]
                )
            )
        if filters.min_score is not None:
            stmt = stmt.where(RiskAssessmentORM.score_value >= filters.min_score)
        if filters.max_score is not None:
            stmt = stmt.where(RiskAssessmentORM.score_value <= filters.max_score)
        if filters.algorithm_version:
            stmt = stmt.where(
                RiskAssessmentORM.algorithm_version == filters.algorithm_version
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(RiskAssessmentORM.last_scored_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_assessment(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Risk assessment search",
            details={"total": total},
        )
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> List[RiskHistory]:
        self._require(assessment_id, tenant_id)
        stmt = (
            select(RiskAssessmentVersionORM)
            .where(
                RiskAssessmentVersionORM.assessment_id == assessment_id,
                RiskAssessmentVersionORM.tenant_id == tenant_id,
            )
            .order_by(RiskAssessmentVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def _require(self, assessment_id: UUID, tenant_id: UUID) -> RiskAssessmentORM:
        row = self._session.get(RiskAssessmentORM, assessment_id)
        if row is None or row.tenant_id != tenant_id:
            raise RiskAssessmentNotFoundError(assessment_id, tenant_id)
        return row
