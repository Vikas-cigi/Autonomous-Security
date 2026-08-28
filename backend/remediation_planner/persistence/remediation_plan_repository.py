"""PostgreSQL-compatible RemediationPlanRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.common import utc_now
from remediation_planner.domain.enums import AuditAction
from remediation_planner.domain.history import RemediationHistory
from remediation_planner.domain.models import RemediationPlan
from remediation_planner.exceptions import RemediationPlanNotFoundError
from remediation_planner.interfaces.remediation_plan_repository import (
    RemediationPlanRepository,
)
from remediation_planner.persistence.mappers import (
    apply_plan_to_orm,
    orm_to_plan,
    plan_to_orm,
    version_from_orm,
)
from remediation_planner.persistence.orm import (
    RemediationHistoryORM,
    RemediationPlanORM,
    RemediationPlanVersionORM,
)
from remediation_planner.query.filters import RemediationPlanSearchFilter
from remediation_planner.query.pagination import Page, PageRequest
from remediation_planner.services.audit import AuditLogger


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresRemediationPlanRepository(RemediationPlanRepository):
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
        plan: RemediationPlan,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Remediation plan persisted",
    ) -> RemediationPlan:
        row = self._session.get(RemediationPlanORM, plan.id)
        created = row is None

        if created:
            existing = self._session.scalars(
                select(RemediationPlanORM).where(
                    RemediationPlanORM.tenant_id == plan.tenant_id,
                    RemediationPlanORM.decision_id == plan.decision_id,
                )
            ).first()
            if existing is not None:
                row = existing
                plan.id = existing.id
                plan.first_planned_at = _ensure_aware(existing.first_planned_at)
                created = False

        if created:
            version = 1
            plan.current_version = version
            plan.touch()
            plan.last_planned_at = utc_now()
            row = plan_to_orm(plan, version=version)
            self._session.add(row)
            action = AuditAction.PLAN_CREATED
        else:
            if row is None or row.tenant_id != plan.tenant_id:
                raise RemediationPlanNotFoundError(plan.id, plan.tenant_id)
            version = int(row.current_version) + 1
            plan.current_version = version
            plan.first_planned_at = _ensure_aware(row.first_planned_at)
            plan.touch()
            plan.last_planned_at = utc_now()
            apply_plan_to_orm(row, plan, version=version)
            action = AuditAction.PLAN_UPDATED

        self._session.flush()
        self._session.add(
            RemediationPlanVersionORM(
                id=uuid4(),
                plan_id=plan.id,
                tenant_id=plan.tenant_id,
                finding_id=plan.finding_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=plan.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.add(
            RemediationHistoryORM(
                id=uuid4(),
                plan_id=plan.id,
                finding_id=plan.finding_id,
                tenant_id=plan.tenant_id,
                action=action.value,
                actor=actor,
                message=change_summary,
                execution_type=plan.execution_type.value,
                details={
                    "version": version,
                    "status": plan.status.value,
                    "steps": len(plan.steps),
                },
                created_at=utc_now(),
            )
        )
        self._audit.log(
            tenant_id=plan.tenant_id,
            action=action,
            message=change_summary,
            actor=actor,
            details={
                "plan_id": str(plan.id),
                "decision_id": str(plan.decision_id),
                "version": version,
            },
        )
        self._session.flush()
        return orm_to_plan(row)

    def get(self, plan_id: UUID, tenant_id: UUID) -> RemediationPlan:
        return orm_to_plan(self._require(plan_id, tenant_id))

    def find_by_finding(
        self, finding_id: UUID, tenant_id: UUID
    ) -> Optional[RemediationPlan]:
        stmt = select(RemediationPlanORM).where(
            RemediationPlanORM.tenant_id == tenant_id,
            RemediationPlanORM.finding_id == finding_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_plan(row) if row else None

    def find_by_decision(
        self, decision_id: UUID, tenant_id: UUID
    ) -> Optional[RemediationPlan]:
        stmt = select(RemediationPlanORM).where(
            RemediationPlanORM.tenant_id == tenant_id,
            RemediationPlanORM.decision_id == decision_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_plan(row) if row else None

    def search(
        self,
        filters: RemediationPlanSearchFilter,
        page: PageRequest,
    ) -> Page[RemediationPlan]:
        stmt = select(RemediationPlanORM).where(
            RemediationPlanORM.tenant_id == filters.tenant_id
        )
        if filters.finding_id:
            stmt = stmt.where(RemediationPlanORM.finding_id == filters.finding_id)
        if filters.decision_id:
            stmt = stmt.where(RemediationPlanORM.decision_id == filters.decision_id)
        if filters.asset_id:
            stmt = stmt.where(RemediationPlanORM.asset_id == filters.asset_id)
        if filters.statuses:
            stmt = stmt.where(
                RemediationPlanORM.status.in_([s.value for s in filters.statuses])
            )
        if filters.execution_types:
            stmt = stmt.where(
                RemediationPlanORM.execution_type.in_(
                    [e.value for e in filters.execution_types]
                )
            )
        if filters.algorithm_version:
            stmt = stmt.where(
                RemediationPlanORM.algorithm_version == filters.algorithm_version
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(RemediationPlanORM.last_planned_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_plan(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Remediation plan search",
            details={"total": total},
        )
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(
        self, plan_id: UUID, tenant_id: UUID
    ) -> List[RemediationHistory]:
        self._require(plan_id, tenant_id)
        stmt = (
            select(RemediationPlanVersionORM)
            .where(
                RemediationPlanVersionORM.plan_id == plan_id,
                RemediationPlanVersionORM.tenant_id == tenant_id,
            )
            .order_by(RemediationPlanVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def _require(self, plan_id: UUID, tenant_id: UUID) -> RemediationPlanORM:
        row = self._session.get(RemediationPlanORM, plan_id)
        if row is None or row.tenant_id != tenant_id:
            raise RemediationPlanNotFoundError(plan_id, tenant_id)
        return row
