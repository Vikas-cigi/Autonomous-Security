"""PostgreSQL-compatible DecisionRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.common import utc_now
from decision_service.domain.enums import AuditAction
from decision_service.domain.history import DecisionVersionRecord
from decision_service.domain.models import DecisionResponse
from decision_service.exceptions import DecisionNotFoundError
from decision_service.interfaces.decision_repository import DecisionRepository
from decision_service.persistence.mappers import (
    apply_decision_to_orm,
    decision_to_orm,
    orm_to_decision,
    version_from_orm,
)
from decision_service.persistence.orm import (
    AuditLogORM,
    DecisionAuditORM,
    DecisionORM,
    DecisionVersionORM,
)
from decision_service.query.filters import DecisionSearchFilter
from decision_service.query.pagination import Page, PageRequest


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresDecisionRepository(DecisionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        response: DecisionResponse,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Decision persisted",
    ) -> DecisionResponse:
        row = self._session.get(DecisionORM, response.id)
        created = row is None

        if created:
            existing = self._session.scalars(
                select(DecisionORM).where(
                    DecisionORM.tenant_id == response.tenant_id,
                    DecisionORM.finding_id == response.finding_id,
                )
            ).first()
            if existing is not None:
                row = existing
                response.id = existing.id
                response.first_decided_at = _ensure_aware(existing.first_decided_at)
                created = False

        if created:
            version = 1
            response.current_version = version
            response.touch()
            response.last_decided_at = utc_now()
            row = decision_to_orm(response, version=version)
            self._session.add(row)
            action = AuditAction.DECISION_CREATED
        else:
            if row is None or row.tenant_id != response.tenant_id:
                raise DecisionNotFoundError(response.id, response.tenant_id)
            version = int(row.current_version) + 1
            response.current_version = version
            response.first_decided_at = _ensure_aware(row.first_decided_at)
            response.touch()
            response.last_decided_at = utc_now()
            apply_decision_to_orm(row, response, version=version)
            action = AuditAction.DECISION_UPDATED

        self._session.flush()
        self._session.add(
            DecisionVersionORM(
                id=uuid4(),
                decision_id=response.id,
                tenant_id=response.tenant_id,
                finding_id=response.finding_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=response.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.add(
            DecisionAuditORM(
                id=uuid4(),
                decision_id=response.id,
                finding_id=response.finding_id,
                tenant_id=response.tenant_id,
                action=action.value,
                actor=actor,
                message=change_summary,
                decision_type=response.recommendation.decision_type.value,
                confidence=response.decision_object.confidence,
                details={
                    "version": version,
                    "status": response.status.value,
                    "policy_verdict": response.policy_verdict,
                },
                created_at=utc_now(),
            )
        )
        self._session.add(
            AuditLogORM(
                id=uuid4(),
                tenant_id=response.tenant_id,
                action=action.value,
                actor=actor,
                message=change_summary,
                details={
                    "decision_id": str(response.id),
                    "finding_id": str(response.finding_id),
                    "version": version,
                },
                success=True,
                created_at=utc_now(),
            )
        )
        self._session.flush()
        return orm_to_decision(row)

    def get(self, decision_id: UUID, tenant_id: UUID) -> DecisionResponse:
        return orm_to_decision(self._require(decision_id, tenant_id))

    def find_by_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[DecisionResponse]:
        stmt = select(DecisionORM).where(
            DecisionORM.tenant_id == tenant_id,
            DecisionORM.finding_id == finding_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_decision(row) if row else None

    def search(
        self,
        filters: DecisionSearchFilter,
        page: PageRequest,
    ) -> Page[DecisionResponse]:
        stmt = select(DecisionORM).where(DecisionORM.tenant_id == filters.tenant_id)
        if filters.finding_id:
            stmt = stmt.where(DecisionORM.finding_id == filters.finding_id)
        if filters.asset_id:
            stmt = stmt.where(DecisionORM.asset_id == filters.asset_id)
        if filters.statuses:
            stmt = stmt.where(
                DecisionORM.status.in_([s.value for s in filters.statuses])
            )
        if filters.decision_types:
            stmt = stmt.where(
                DecisionORM.decision_type.in_(
                    [d.value for d in filters.decision_types]
                )
            )
        if filters.min_confidence is not None:
            stmt = stmt.where(DecisionORM.confidence >= filters.min_confidence)
        if filters.max_confidence is not None:
            stmt = stmt.where(DecisionORM.confidence <= filters.max_confidence)
        if filters.algorithm_version:
            stmt = stmt.where(
                DecisionORM.algorithm_version == filters.algorithm_version
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(DecisionORM.last_decided_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_decision(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(
        self,
        decision_id: UUID,
        tenant_id: UUID,
    ) -> List[DecisionVersionRecord]:
        self._require(decision_id, tenant_id)
        stmt = (
            select(DecisionVersionORM)
            .where(
                DecisionVersionORM.decision_id == decision_id,
                DecisionVersionORM.tenant_id == tenant_id,
            )
            .order_by(DecisionVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def _require(self, decision_id: UUID, tenant_id: UUID) -> DecisionORM:
        row = self._session.get(DecisionORM, decision_id)
        if row is None or row.tenant_id != tenant_id:
            raise DecisionNotFoundError(decision_id, tenant_id)
        return row
