"""PostgreSQL-compatible VerificationHistoryRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verification_engine.domain.history import VerificationHistory
from verification_engine.interfaces.verification_history_repository import (
    VerificationHistoryRepository,
)
from verification_engine.persistence.mappers import version_from_orm
from verification_engine.persistence.orm import VerificationVersionORM


class PostgresVerificationHistoryRepository(VerificationHistoryRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, history: VerificationHistory) -> VerificationHistory:
        row = VerificationVersionORM(
            id=history.id,
            verification_id=history.verification_id,
            tenant_id=history.tenant_id,
            execution_id=history.execution_id,
            version=history.version,
            change_summary=history.change_summary,
            created_by=history.created_by,
            payload=history.snapshot.model_dump(mode="json"),
            created_at=history.created_at,
        )
        self._session.add(row)
        self._session.flush()
        return version_from_orm(row)

    def list_for_verification(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationHistory]:
        stmt = (
            select(VerificationVersionORM)
            .where(
                VerificationVersionORM.verification_id == verification_id,
                VerificationVersionORM.tenant_id == tenant_id,
            )
            .order_by(VerificationVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def get_version(
        self, verification_id: UUID, tenant_id: UUID, version: int
    ) -> Optional[VerificationHistory]:
        stmt = select(VerificationVersionORM).where(
            VerificationVersionORM.verification_id == verification_id,
            VerificationVersionORM.tenant_id == tenant_id,
            VerificationVersionORM.version == version,
        )
        row = self._session.scalars(stmt).first()
        return version_from_orm(row) if row else None
