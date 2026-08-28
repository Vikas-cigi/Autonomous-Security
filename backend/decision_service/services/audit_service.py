"""DecisionAuditService — append audit records via repository port."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from decision_service.domain.enums import AuditAction
from decision_service.domain.history import DecisionAuditRecord
from decision_service.interfaces.decision_audit_repository import DecisionAuditRepository


class DecisionAuditService:
    """Thin facade over DecisionAuditRepository for orchestration events."""

    def __init__(self, audit_repository: DecisionAuditRepository) -> None:
        self._repo = audit_repository

    def record(
        self,
        *,
        action: AuditAction,
        message: str,
        tenant_id: Optional[UUID] = None,
        decision_id: Optional[UUID] = None,
        finding_id: Optional[UUID] = None,
        actor: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        decision_type: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> DecisionAuditRecord:
        record = DecisionAuditRecord(
            decision_id=decision_id,
            finding_id=finding_id,
            tenant_id=tenant_id,
            action=action,
            actor=actor,
            message=message,
            details=details or {},
            decision_type=decision_type,
            confidence=confidence,
        )
        return self._repo.append(record)
