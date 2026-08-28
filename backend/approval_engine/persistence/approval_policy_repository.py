"""PostgreSQL-compatible ApprovalPolicyRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from approval_engine.domain.models import ApprovalPolicy
from approval_engine.exceptions import ApprovalPolicyNotFoundError
from approval_engine.interfaces.approval_policy_repository import (
    ApprovalPolicyRepository,
)
from approval_engine.persistence.mappers import (
    apply_policy_to_orm,
    orm_to_policy,
    policy_to_orm,
)
from approval_engine.persistence.orm import ApprovalPolicyORM
from approval_engine.query.filters import ApprovalPolicySearchFilter
from approval_engine.query.pagination import Page, PageRequest


class PostgresApprovalPolicyRepository(ApprovalPolicyRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, policy: ApprovalPolicy) -> ApprovalPolicy:
        row = self._session.get(ApprovalPolicyORM, policy.id)
        if row is None:
            policy.touch()
            row = policy_to_orm(policy)
            self._session.add(row)
        else:
            if row.tenant_id != policy.tenant_id:
                raise ApprovalPolicyNotFoundError(policy.id, policy.tenant_id)
            policy.touch()
            apply_policy_to_orm(row, policy)
        self._session.flush()
        return orm_to_policy(row)

    def get(self, policy_id: UUID, tenant_id: UUID) -> ApprovalPolicy:
        row = self._session.get(ApprovalPolicyORM, policy_id)
        if row is None or row.tenant_id != tenant_id:
            raise ApprovalPolicyNotFoundError(policy_id, tenant_id)
        return orm_to_policy(row)

    def find_default(self, tenant_id: UUID) -> Optional[ApprovalPolicy]:
        stmt = (
            select(ApprovalPolicyORM)
            .where(
                ApprovalPolicyORM.tenant_id == tenant_id,
                ApprovalPolicyORM.enabled.is_(True),
            )
            .order_by(ApprovalPolicyORM.updated_at.desc())
        )
        row = self._session.scalars(stmt).first()
        return orm_to_policy(row) if row else None

    def search(
        self,
        filters: ApprovalPolicySearchFilter,
        page: PageRequest,
    ) -> Page[ApprovalPolicy]:
        stmt = select(ApprovalPolicyORM).where(
            ApprovalPolicyORM.tenant_id == filters.tenant_id
        )
        if filters.enabled is not None:
            stmt = stmt.where(ApprovalPolicyORM.enabled == filters.enabled)
        if filters.name_contains:
            stmt = stmt.where(
                ApprovalPolicyORM.name.ilike(f"%{filters.name_contains}%")
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ApprovalPolicyORM.updated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_policy(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)

    def list_for_tenant(self, tenant_id: UUID) -> List[ApprovalPolicy]:
        stmt = (
            select(ApprovalPolicyORM)
            .where(ApprovalPolicyORM.tenant_id == tenant_id)
            .order_by(ApprovalPolicyORM.name.asc())
        )
        return [orm_to_policy(r) for r in self._session.scalars(stmt).all()]
