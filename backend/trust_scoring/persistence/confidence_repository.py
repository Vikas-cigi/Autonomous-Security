"""PostgreSQL-compatible ConfidenceRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from trust_scoring.domain.enums import AuditAction
from trust_scoring.domain.models import ConfidenceFactor
from trust_scoring.exceptions import TrustAssessmentNotFoundError
from trust_scoring.interfaces.confidence_repository import ConfidenceRepository
from trust_scoring.persistence.mappers import factor_to_orm, orm_to_factor
from trust_scoring.persistence.orm import ConfidenceFactorORM, TrustAssessmentORM
from trust_scoring.query.filters import ConfidenceFactorSearchFilter
from trust_scoring.query.pagination import Page, PageRequest
from trust_scoring.services.audit import AuditLogger


class PostgresConfidenceRepository(ConfidenceRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def replace_factors(
        self,
        *,
        assessment_id: UUID,
        tenant_id: UUID,
        finding_id: UUID,
        factors: List[ConfidenceFactor],
        actor: Optional[str] = None,
    ) -> List[ConfidenceFactor]:
        self._require_assessment(assessment_id, tenant_id)
        self._session.execute(
            delete(ConfidenceFactorORM).where(
                ConfidenceFactorORM.assessment_id == assessment_id,
                ConfidenceFactorORM.tenant_id == tenant_id,
            )
        )
        rows = [
            factor_to_orm(
                factor,
                assessment_id=assessment_id,
                tenant_id=tenant_id,
                finding_id=finding_id,
            )
            for factor in factors
        ]
        self._session.add_all(rows)
        self._session.flush()
        self._audit.log(
            tenant_id=tenant_id,
            action=AuditAction.FACTOR_RECORDED,
            message=f"Replaced {len(factors)} confidence factors",
            actor=actor,
            details={
                "assessment_id": str(assessment_id),
                "finding_id": str(finding_id),
                "count": len(factors),
            },
        )
        return [orm_to_factor(r) for r in rows]

    def list_factors(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> List[ConfidenceFactor]:
        self._require_assessment(assessment_id, tenant_id)
        stmt = (
            select(ConfidenceFactorORM)
            .where(
                ConfidenceFactorORM.assessment_id == assessment_id,
                ConfidenceFactorORM.tenant_id == tenant_id,
            )
            .order_by(ConfidenceFactorORM.category.asc(), ConfidenceFactorORM.label.asc())
        )
        return [orm_to_factor(r) for r in self._session.scalars(stmt).all()]

    def search_factors(
        self,
        filters: ConfidenceFactorSearchFilter,
        page: PageRequest,
    ) -> Page[ConfidenceFactor]:
        stmt = select(ConfidenceFactorORM).where(
            ConfidenceFactorORM.tenant_id == filters.tenant_id
        )
        if filters.assessment_id:
            stmt = stmt.where(
                ConfidenceFactorORM.assessment_id == filters.assessment_id
            )
        if filters.finding_id:
            stmt = stmt.where(ConfidenceFactorORM.finding_id == filters.finding_id)
        if filters.categories:
            stmt = stmt.where(ConfidenceFactorORM.category.in_(filters.categories))
        if filters.polarity:
            stmt = stmt.where(ConfidenceFactorORM.polarity == filters.polarity)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ConfidenceFactorORM.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_factor(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)

    def _require_assessment(self, assessment_id: UUID, tenant_id: UUID) -> None:
        row = self._session.get(TrustAssessmentORM, assessment_id)
        if row is None or row.tenant_id != tenant_id:
            raise TrustAssessmentNotFoundError(assessment_id, tenant_id)
