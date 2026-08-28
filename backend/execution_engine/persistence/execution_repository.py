"""PostgreSQL-compatible ExecutionRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.common import utc_now
from execution_engine.domain.enums import AuditAction
from execution_engine.domain.history import ExecutionHistory
from execution_engine.domain.models import ExecutionResult
from execution_engine.exceptions import ExecutionNotFoundError
from execution_engine.interfaces.execution_repository import ExecutionRepository
from execution_engine.persistence.mappers import (
    apply_result_to_orm,
    orm_to_result,
    result_to_orm,
    version_from_orm,
)
from execution_engine.persistence.orm import (
    ExecutionAuditORM,
    ExecutionResultORM,
    ExecutionVersionORM,
)
from execution_engine.query.filters import ExecutionSearchFilter
from execution_engine.query.pagination import Page, PageRequest
from execution_engine.services.audit_logger import AuditLogger


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresExecutionRepository(ExecutionRepository):
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
        result: ExecutionResult,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Execution persisted",
    ) -> ExecutionResult:
        row = self._session.get(ExecutionResultORM, result.id)
        created = row is None

        if created:
            existing = self._session.scalars(
                select(ExecutionResultORM).where(
                    ExecutionResultORM.tenant_id == result.tenant_id,
                    ExecutionResultORM.plan_id == result.plan_id,
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
            action = AuditAction.EXECUTION_CREATED
        else:
            if row is None or row.tenant_id != result.tenant_id:
                raise ExecutionNotFoundError(result.id, result.tenant_id)
            version = int(row.current_version) + 1
            result.current_version = version
            if row.first_started_at:
                result.first_started_at = _ensure_aware(row.first_started_at)
            result.touch()
            result.last_evaluated_at = utc_now()
            apply_result_to_orm(row, result, version=version)
            action = AuditAction.EXECUTION_COMPLETED if result.is_terminal else AuditAction.STEP_EXECUTED

        self._session.flush()
        self._session.add(
            ExecutionVersionORM(
                id=uuid4(),
                execution_id=result.id,
                tenant_id=result.tenant_id,
                plan_id=result.plan_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=result.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.add(
            ExecutionAuditORM(
                id=uuid4(),
                execution_id=result.id,
                plan_id=result.plan_id,
                finding_id=result.finding_id,
                approval_id=result.approval_id,
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
                "execution_id": str(result.id),
                "plan_id": str(result.plan_id),
                "version": version,
                "status": result.status.value,
            },
        )
        self._session.flush()
        return orm_to_result(row)

    def get(self, execution_id: UUID, tenant_id: UUID) -> ExecutionResult:
        return orm_to_result(self._require(execution_id, tenant_id))

    def find_by_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> Optional[ExecutionResult]:
        stmt = select(ExecutionResultORM).where(
            ExecutionResultORM.tenant_id == tenant_id,
            ExecutionResultORM.plan_id == plan_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_result(row) if row else None

    def search(
        self,
        filters: ExecutionSearchFilter,
        page: PageRequest,
    ) -> Page[ExecutionResult]:
        stmt = select(ExecutionResultORM).where(
            ExecutionResultORM.tenant_id == filters.tenant_id
        )
        if filters.plan_id:
            stmt = stmt.where(ExecutionResultORM.plan_id == filters.plan_id)
        if filters.finding_id:
            stmt = stmt.where(ExecutionResultORM.finding_id == filters.finding_id)
        if filters.decision_id:
            stmt = stmt.where(ExecutionResultORM.decision_id == filters.decision_id)
        if filters.approval_id:
            stmt = stmt.where(ExecutionResultORM.approval_id == filters.approval_id)
        if filters.statuses:
            stmt = stmt.where(
                ExecutionResultORM.status.in_([s.value for s in filters.statuses])
            )
        if filters.queue_name:
            stmt = stmt.where(ExecutionResultORM.queue_name == filters.queue_name)
        if filters.algorithm_version:
            stmt = stmt.where(
                ExecutionResultORM.algorithm_version == filters.algorithm_version
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ExecutionResultORM.last_evaluated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_result(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Execution search",
            details={"total": total},
        )
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(
        self, execution_id: UUID, tenant_id: UUID
    ) -> List[ExecutionHistory]:
        self._require(execution_id, tenant_id)
        stmt = (
            select(ExecutionVersionORM)
            .where(
                ExecutionVersionORM.execution_id == execution_id,
                ExecutionVersionORM.tenant_id == tenant_id,
            )
            .order_by(ExecutionVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def _require(self, execution_id: UUID, tenant_id: UUID) -> ExecutionResultORM:
        row = self._session.get(ExecutionResultORM, execution_id)
        if row is None or row.tenant_id != tenant_id:
            raise ExecutionNotFoundError(execution_id, tenant_id)
        return row
