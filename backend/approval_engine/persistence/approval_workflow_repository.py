"""PostgreSQL-compatible ApprovalWorkflowRepository."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from approval_engine.domain.models import ApprovalWorkflow
from approval_engine.exceptions import ApprovalNotFoundError
from approval_engine.interfaces.approval_workflow_repository import (
    ApprovalWorkflowRepository,
)
from approval_engine.persistence.mappers import apply_request_to_orm, orm_to_request
from approval_engine.persistence.orm import ApprovalRequestORM
from models.common import utc_now


class PostgresApprovalWorkflowRepository(ApprovalWorkflowRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self, approval_id: UUID, tenant_id: UUID, workflow: ApprovalWorkflow
    ) -> ApprovalWorkflow:
        row = self._session.get(ApprovalRequestORM, approval_id)
        if row is None or row.tenant_id != tenant_id:
            raise ApprovalNotFoundError(approval_id, tenant_id)
        request = orm_to_request(row)
        request.workflow = workflow
        request.touch()
        request.last_evaluated_at = utc_now()
        apply_request_to_orm(row, request, version=int(row.current_version))
        self._session.flush()
        return orm_to_request(row).workflow

    def get(
        self, approval_id: UUID, tenant_id: UUID
    ) -> Optional[ApprovalWorkflow]:
        row = self._session.get(ApprovalRequestORM, approval_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return orm_to_request(row).workflow
