"""Execution audit service — append and query governance audit records."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from execution_engine.domain.enums import AuditAction
from execution_engine.domain.history import ExecutionAuditRecord
from execution_engine.interfaces.execution_audit_repository import (
    ExecutionAuditRepository,
)
from execution_engine.query.filters import ExecutionAuditSearchFilter
from execution_engine.query.pagination import Page, PageRequest


class ExecutionAuditService:
    def __init__(
        self, audit_repository: Optional[ExecutionAuditRepository] = None
    ) -> None:
        self._repo = audit_repository

    def record(
        self,
        *,
        action: AuditAction,
        message: str,
        execution_id: Optional[UUID] = None,
        plan_id: Optional[UUID] = None,
        finding_id: Optional[UUID] = None,
        approval_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        actor: Optional[str] = None,
        status: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[ExecutionAuditRecord]:
        record = ExecutionAuditRecord(
            execution_id=execution_id,
            plan_id=plan_id,
            finding_id=finding_id,
            approval_id=approval_id,
            tenant_id=tenant_id,
            action=action,
            actor=actor,
            message=message,
            details=details or {},
            status=status,
        )
        if self._repo is None:
            return record
        return self._repo.append(record)

    def list_for_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> List[ExecutionAuditRecord]:
        if self._repo is None:
            return []
        return self._repo.list_for_execution(execution_id, tenant_id)

    def search(
        self,
        filters: ExecutionAuditSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[ExecutionAuditRecord]:
        if self._repo is None:
            return Page.from_items([], request=page or PageRequest(), total_items=0)
        return self._repo.search(filters, page or PageRequest())
