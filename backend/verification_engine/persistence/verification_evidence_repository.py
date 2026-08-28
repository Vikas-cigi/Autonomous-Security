"""PostgreSQL-compatible VerificationEvidenceRepository."""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from verification_engine.domain.models import VerificationEvidence
from verification_engine.interfaces.verification_evidence_repository import (
    VerificationEvidenceRepository,
)
from verification_engine.persistence.mappers import evidence_from_orm, evidence_to_orm
from verification_engine.persistence.orm import VerificationEvidenceORM
from verification_engine.query.filters import VerificationEvidenceSearchFilter
from verification_engine.query.pagination import Page, PageRequest


class PostgresVerificationEvidenceRepository(VerificationEvidenceRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_many(
        self,
        verification_id: UUID,
        tenant_id: UUID,
        evidence: List[VerificationEvidence],
    ) -> List[VerificationEvidence]:
        self._session.execute(
            delete(VerificationEvidenceORM).where(
                VerificationEvidenceORM.verification_id == verification_id,
                VerificationEvidenceORM.tenant_id == tenant_id,
            )
        )
        rows = [
            evidence_to_orm(e, verification_id=verification_id, tenant_id=tenant_id)
            for e in evidence
        ]
        self._session.add_all(rows)
        self._session.flush()
        return [evidence_from_orm(r) for r in rows]

    def list_for_verification(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationEvidence]:
        stmt = (
            select(VerificationEvidenceORM)
            .where(
                VerificationEvidenceORM.verification_id == verification_id,
                VerificationEvidenceORM.tenant_id == tenant_id,
            )
            .order_by(VerificationEvidenceORM.collected_at.asc())
        )
        return [evidence_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search(
        self,
        filters: VerificationEvidenceSearchFilter,
        page: PageRequest,
    ) -> Page[VerificationEvidence]:
        stmt = select(VerificationEvidenceORM).where(
            VerificationEvidenceORM.tenant_id == filters.tenant_id
        )
        if filters.verification_id:
            stmt = stmt.where(
                VerificationEvidenceORM.verification_id == filters.verification_id
            )
        if filters.phase:
            stmt = stmt.where(VerificationEvidenceORM.phase == filters.phase)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(VerificationEvidenceORM.collected_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [evidence_from_orm(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)
