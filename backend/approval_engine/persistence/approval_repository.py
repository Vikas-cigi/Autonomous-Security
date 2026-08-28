"""PostgreSQL-compatible ApprovalRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.common import utc_now
from approval_engine.domain.enums import AuditAction
from approval_engine.domain.history import ApprovalHistory
from approval_engine.domain.models import ApprovalRequest
from approval_engine.exceptions import ApprovalNotFoundError
from approval_engine.interfaces.approval_repository import ApprovalRepository
from approval_engine.persistence.mappers import (
    apply_request_to_orm,
    orm_to_request,
    request_to_orm,
    version_from_orm,
)
from approval_engine.persistence.orm import (
    ApprovalAuditORM,
    ApprovalRequestORM,
    ApprovalVersionORM,
)
from approval_engine.query.filters import ApprovalSearchFilter
from approval_engine.query.pagination import Page, PageRequest
from approval_engine.services.audit_logger import AuditLogger


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresApprovalRepository(ApprovalRepository):
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
        request: ApprovalRequest,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Approval request persisted",
    ) -> ApprovalRequest:
        row = self._session.get(ApprovalRequestORM, request.id)
        created = row is None

        if created:
            existing = self._session.scalars(
                select(ApprovalRequestORM).where(
                    ApprovalRequestORM.tenant_id == request.tenant_id,
                    ApprovalRequestORM.plan_id == request.plan_id,
                )
            ).first()
            if existing is not None:
                row = existing
                request.id = existing.id
                request.first_requested_at = _ensure_aware(existing.first_requested_at)
                created = False

        if created:
            version = 1
            request.current_version = version
            request.touch()
            request.last_evaluated_at = utc_now()
            row = request_to_orm(request, version=version)
            self._session.add(row)
            action = AuditAction.REQUEST_CREATED
        else:
            if row is None or row.tenant_id != request.tenant_id:
                raise ApprovalNotFoundError(request.id, request.tenant_id)
            version = int(row.current_version) + 1
            request.current_version = version
            request.first_requested_at = _ensure_aware(row.first_requested_at)
            request.touch()
            request.last_evaluated_at = utc_now()
            apply_request_to_orm(row, request, version=version)
            action = AuditAction.REQUEST_UPDATED

        self._session.flush()
        self._session.add(
            ApprovalVersionORM(
                id=uuid4(),
                approval_id=request.id,
                tenant_id=request.tenant_id,
                plan_id=request.plan_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=request.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.add(
            ApprovalAuditORM(
                id=uuid4(),
                approval_id=request.id,
                plan_id=request.plan_id,
                finding_id=request.finding_id,
                tenant_id=request.tenant_id,
                action=action.value,
                actor=actor,
                message=change_summary,
                state=request.state.value,
                details={"version": version},
                created_at=utc_now(),
            )
        )
        self._audit.log(
            tenant_id=request.tenant_id,
            action=action,
            message=change_summary,
            actor=actor,
            details={
                "approval_id": str(request.id),
                "plan_id": str(request.plan_id),
                "version": version,
                "state": request.state.value,
            },
        )
        self._session.flush()
        return orm_to_request(row)

    def get(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest:
        return orm_to_request(self._require(approval_id, tenant_id))

    def find_by_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> Optional[ApprovalRequest]:
        stmt = select(ApprovalRequestORM).where(
            ApprovalRequestORM.tenant_id == tenant_id,
            ApprovalRequestORM.plan_id == plan_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_request(row) if row else None

    def search(
        self,
        filters: ApprovalSearchFilter,
        page: PageRequest,
    ) -> Page[ApprovalRequest]:
        stmt = select(ApprovalRequestORM).where(
            ApprovalRequestORM.tenant_id == filters.tenant_id
        )
        if filters.plan_id:
            stmt = stmt.where(ApprovalRequestORM.plan_id == filters.plan_id)
        if filters.finding_id:
            stmt = stmt.where(ApprovalRequestORM.finding_id == filters.finding_id)
        if filters.decision_id:
            stmt = stmt.where(ApprovalRequestORM.decision_id == filters.decision_id)
        if filters.simulation_id:
            stmt = stmt.where(
                ApprovalRequestORM.simulation_id == filters.simulation_id
            )
        if filters.states:
            stmt = stmt.where(
                ApprovalRequestORM.state.in_([s.value for s in filters.states])
            )
        if filters.emergency is not None:
            stmt = stmt.where(ApprovalRequestORM.emergency == filters.emergency)
        if filters.algorithm_version:
            stmt = stmt.where(
                ApprovalRequestORM.algorithm_version == filters.algorithm_version
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ApprovalRequestORM.last_evaluated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_request(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Approval search",
            details={"total": total},
        )
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(
        self, approval_id: UUID, tenant_id: UUID
    ) -> List[ApprovalHistory]:
        self._require(approval_id, tenant_id)
        stmt = (
            select(ApprovalVersionORM)
            .where(
                ApprovalVersionORM.approval_id == approval_id,
                ApprovalVersionORM.tenant_id == tenant_id,
            )
            .order_by(ApprovalVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def _require(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequestORM:
        row = self._session.get(ApprovalRequestORM, approval_id)
        if row is None or row.tenant_id != tenant_id:
            raise ApprovalNotFoundError(approval_id, tenant_id)
        return row
