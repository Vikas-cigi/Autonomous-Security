"""Approval audit service — append and query governance audit records."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from approval_engine.domain.enums import AuditAction
from approval_engine.domain.history import ApprovalAuditRecord
from approval_engine.interfaces.approval_audit_repository import (
    ApprovalAuditRepository,
)
from approval_engine.query.filters import ApprovalAuditSearchFilter
from approval_engine.query.pagination import Page, PageRequest


class ApprovalAuditService:
    def __init__(self, audit_repository: Optional[ApprovalAuditRepository] = None) -> None:
        self._repo = audit_repository

    def record(
        self,
        *,
        action: AuditAction,
        message: str,
        approval_id: Optional[UUID] = None,
        plan_id: Optional[UUID] = None,
        finding_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        actor: Optional[str] = None,
        state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[ApprovalAuditRecord]:
        record = ApprovalAuditRecord(
            approval_id=approval_id,
            plan_id=plan_id,
            finding_id=finding_id,
            tenant_id=tenant_id,
            action=action,
            actor=actor,
            message=message,
            details=details or {},
            state=state,
        )
        if self._repo is None:
            return record
        return self._repo.append(record)

    def list_for_approval(
        self, approval_id: UUID, tenant_id: UUID
    ) -> List[ApprovalAuditRecord]:
        if self._repo is None:
            return []
        return self._repo.list_for_approval(approval_id, tenant_id)

    def search(
        self,
        filters: ApprovalAuditSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[ApprovalAuditRecord]:
        if self._repo is None:
            return Page.from_items([], request=page or PageRequest(), total_items=0)
        return self._repo.search(filters, page or PageRequest())
