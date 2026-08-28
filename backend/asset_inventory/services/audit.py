"""Audit logging for Asset Inventory operations."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from models.common import utc_now
from asset_inventory.domain.enums import AuditAction
from asset_inventory.persistence.orm import AuditLogORM

logger = logging.getLogger(__name__)


class AuditLogger:
    """Persists inventory-wide audit events and emits structured logs."""

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
            "asset_inventory.audit action=%s tenant=%s actor=%s message=%s",
            action.value,
            tenant_id,
            actor,
            message,
        )
