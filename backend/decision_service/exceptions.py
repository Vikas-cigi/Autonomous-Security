"""Enterprise Decision Service exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class DecisionServiceError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class DecisionNotFoundError(DecisionServiceError):
    def __init__(self, decision_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Decision {decision_id} not found for tenant {tenant_id}",
            details={
                "decision_id": str(decision_id),
                "tenant_id": str(tenant_id),
            },
        )


class InvalidDecisionRequestError(DecisionServiceError):
    """Raised when a DecisionRequest fails structural or business validation."""


class DecisionPolicyDeniedError(DecisionServiceError):
    """Raised when policy evaluation denies finalizing a decision."""


class AIOrchestrationError(DecisionServiceError):
    """Raised when Context Manager / Prompt Builder / Provider orchestration fails."""
