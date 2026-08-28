"""Approval Engine exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class ApprovalEngineError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class ApprovalNotFoundError(ApprovalEngineError):
    def __init__(self, approval_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Approval {approval_id} not found for tenant {tenant_id}",
            details={
                "approval_id": str(approval_id),
                "tenant_id": str(tenant_id),
            },
        )


class ApprovalPolicyNotFoundError(ApprovalEngineError):
    def __init__(self, policy_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Approval policy {policy_id} not found for tenant {tenant_id}",
            details={
                "policy_id": str(policy_id),
                "tenant_id": str(tenant_id),
            },
        )


class InvalidApprovalRequestError(ApprovalEngineError):
    """Raised when approval inputs fail structural or business validation."""


class ApprovalStateError(ApprovalEngineError):
    """Raised when an operation is illegal for the current approval state."""
