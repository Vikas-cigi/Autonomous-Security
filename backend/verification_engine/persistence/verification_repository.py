"""PostgreSQL-compatible VerificationRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.common import utc_now
from verification_engine.domain.enums import AuditAction
from verification_engine.domain.history import VerificationHistory
from verification_engine.domain.models import VerificationResult
from verification_engine.exceptions import VerificationNotFoundError
from verification_engine.interfaces.verification_repository import VerificationRepository
from verification_engine.persistence.mappers import (
    apply_result_to_orm,
    orm_to_result,
    result_to_orm,
    version_from_orm,
)
from verification_engine.persistence.orm import (
    VerificationAuditORM,
    VerificationResultORM,
    VerificationVersionORM,
)
from verification_engine.query.filters import VerificationSearchFilter
from verification_engine.query.pagination import Page, PageRequest
from verification_engine.services.audit_logger import AuditLogger


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresVerificationRepository(VerificationRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def save(
        self,
        result: VerificationResult,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Verification persisted",
    ) -> VerificationResult:
        row = self._session.get(VerificationResultORM, result.id)
        created = row is None

        if created:
            existing = self._session.scalars(
                select(VerificationResultORM).where(
                    VerificationResultORM.tenant_id == result.tenant_id,
                    VerificationResultORM.execution_id == result.execution_id,
                )
            ).first()
            if existing is not None:
                row = existing
                result.id = existing.id
                if existing.first_started_at:
                    result.first_started_at = _ensure_aware(existing.first_started_at)
                created = False

        if created:
            version = 1
            result.current_version = version
            result.touch()
            result.last_evaluated_at = utc_now()
            row = result_to_orm(result, version=version)
            self._session.add(row)
            action = AuditAction.VERIFICATION_CREATED
        else:
            if row is None or row.tenant_id != result.tenant_id:
                raise VerificationNotFoundError(result.id, result.tenant_id)
            version = int(row.current_version) + 1
            result.current_version = version
            if row.first_started_at:
                result.first_started_at = _ensure_aware(row.first_started_at)
            result.touch()
            result.last_evaluated_at = utc_now()
            apply_result_to_orm(row, result, version=version)
            if result.status.value == "cancelled":
                action = AuditAction.VERIFICATION_CANCELLED
            elif result.is_terminal and result.status.value in {
                "verified",
                "completed",
            }:
                action = AuditAction.VERIFICATION_COMPLETED
            elif result.is_terminal:
                action = AuditAction.VERIFICATION_FAILED
            else:
                action = AuditAction.VERIFICATION_STARTED

        self._session.flush()
        self._session.add(
            VerificationVersionORM(
                id=uuid4(),
                verification_id=result.id,
                tenant_id=result.tenant_id,
                execution_id=result.execution_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=result.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.add(
            VerificationAuditORM(
                id=uuid4(),
                verification_id=result.id,
                execution_id=result.execution_id,
                finding_id=result.finding_id,
                plan_id=result.plan_id,
                tenant_id=result.tenant_id,
                action=action.value,
                actor=actor,
                message=change_summary,
                status=result.status.value,
                details={"version": version},
                created_at=utc_now(),
            )
        )
        self._audit.log(
            tenant_id=result.tenant_id,
            action=action,
            message=change_summary,
            actor=actor,
            details={
                "verification_id": str(result.id),
                "execution_id": str(result.execution_id),
                "version": version,
                "status": result.status.value,
            },
        )
        self._session.flush()
        return orm_to_result(row)

    def get(self, verification_id: UUID, tenant_id: UUID) -> VerificationResult:
        return orm_to_result(self._require(verification_id, tenant_id))

    def find_by_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> Optional[VerificationResult]:
        stmt = select(VerificationResultORM).where(
            VerificationResultORM.tenant_id == tenant_id,
            VerificationResultORM.execution_id == execution_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_result(row) if row else None

    def find_by_finding(
        self, finding_id: UUID, tenant_id: UUID
    ) -> Optional[VerificationResult]:
        stmt = (
            select(VerificationResultORM)
            .where(
                VerificationResultORM.tenant_id == tenant_id,
                VerificationResultORM.finding_id == finding_id,
            )
            .order_by(VerificationResultORM.last_evaluated_at.desc())
        )
        row = self._session.scalars(stmt).first()
        return orm_to_result(row) if row else None

    def search(
        self,
        filters: VerificationSearchFilter,
        page: PageRequest,
    ) -> Page[VerificationResult]:
        stmt = select(VerificationResultORM).where(
            VerificationResultORM.tenant_id == filters.tenant_id
        )
        if filters.execution_id:
            stmt = stmt.where(
                VerificationResultORM.execution_id == filters.execution_id
            )
        if filters.plan_id:
            stmt = stmt.where(VerificationResultORM.plan_id == filters.plan_id)
        if filters.finding_id:
            stmt = stmt.where(VerificationResultORM.finding_id == filters.finding_id)
        if filters.decision_id:
            stmt = stmt.where(VerificationResultORM.decision_id == filters.decision_id)
        if filters.statuses:
            stmt = stmt.where(
                VerificationResultORM.status.in_([s.value for s in filters.statuses])
            )
        if filters.algorithm_version:
            stmt = stmt.where(
                VerificationResultORM.algorithm_version == filters.algorithm_version
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(VerificationResultORM.last_evaluated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_result(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Verification search",
            details={"total": total},
        )
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationHistory]:
        self._require(verification_id, tenant_id)
        stmt = (
            select(VerificationVersionORM)
            .where(
                VerificationVersionORM.verification_id == verification_id,
                VerificationVersionORM.tenant_id == tenant_id,
            )
            .order_by(VerificationVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def _require(self, verification_id: UUID, tenant_id: UUID) -> VerificationResultORM:
        row = self._session.get(VerificationResultORM, verification_id)
        if row is None or row.tenant_id != tenant_id:
            raise VerificationNotFoundError(verification_id, tenant_id)
        return row
