"""Audit logging service for Evidence Repository operations."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from models.common import utc_now
from evidence_repository.domain.enums import AuditAction
from evidence_repository.persistence.orm import AuditLogORM

logger = logging.getLogger(__name__)


class AuditLogger:
    """Persists repository-wide audit events and emits structured logs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def log(
        self,
        *,
        tenant_id: Optional[UUID],
        action: AuditAction,
        message: str,
        actor: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> None:
        """Write an audit log row and mirror to application logs."""

        entry = AuditLogORM(
            id=uuid4(),
            tenant_id=tenant_id,
            action=action.value,
            actor=actor,
            message=message,
            details=details or {},
            success=success,
            created_at=utc_now(),
        )
        self._session.add(entry)
        log_fn = logger.info if success else logger.error
        log_fn(
            "evidence_repo.audit action=%s tenant=%s actor=%s message=%s",
            action.value,
            tenant_id,
            actor,
            message,
        )
