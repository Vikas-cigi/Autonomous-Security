"""Audit logging for Remediation Planner operations."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from models.common import utc_now
from remediation_planner.domain.enums import AuditAction
from remediation_planner.persistence.orm import AuditLogORM

logger = logging.getLogger(__name__)


class AuditLogger:
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
        self._session.add(
            AuditLogORM(
                id=uuid4(),
                tenant_id=tenant_id,
                action=action.value,
                actor=actor,
                message=message,
                details=details or {},
                success=success,
                created_at=utc_now(),
            )
        )
        log_fn = logger.info if success else logger.error
        log_fn(
            "remediation_planner.audit action=%s tenant=%s actor=%s message=%s",
            action.value,
            tenant_id,
            actor,
            message,
        )
