"""Verification audit recording service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from verification_engine.domain.enums import AuditAction
from verification_engine.domain.history import VerificationAuditRecord
from verification_engine.interfaces.verification_audit_repository import (
    VerificationAuditRepository,
)
from verification_engine.query.filters import VerificationAuditSearchFilter
from verification_engine.query.pagination import Page, PageRequest


class VerificationAuditService:
    def __init__(
        self,
        audit_repository: Optional[VerificationAuditRepository] = None,
    ) -> None:
        self._repo = audit_repository

    def record(
        self,
        *,
        action: AuditAction,
        message: str,
        verification_id: Optional[UUID] = None,
        execution_id: Optional[UUID] = None,
        finding_id: Optional[UUID] = None,
        plan_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        actor: Optional[str] = None,
        status: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[VerificationAuditRecord]:
        record = VerificationAuditRecord(
            verification_id=verification_id,
            execution_id=execution_id,
            finding_id=finding_id,
            plan_id=plan_id,
            tenant_id=tenant_id,
            action=action,
            actor=actor,
            message=message,
            status=status,
            details=details or {},
        )
        if self._repo is None:
            return record
        return self._repo.append(record)

    def list_for_verification(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationAuditRecord]:
        if self._repo is None:
            return []
        return self._repo.list_for_verification(verification_id, tenant_id)

    def search(
        self,
        filters: VerificationAuditSearchFilter,
        page: PageRequest,
    ) -> Page[VerificationAuditRecord]:
        if self._repo is None:
            return Page.from_items([], request=page, total_items=0)
        return self._repo.search(filters, page)
