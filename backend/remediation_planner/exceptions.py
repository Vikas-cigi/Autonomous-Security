"""Remediation Planner exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class RemediationPlannerError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class RemediationPlanNotFoundError(RemediationPlannerError):
    def __init__(self, plan_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Remediation plan {plan_id} not found for tenant {tenant_id}",
            details={"plan_id": str(plan_id), "tenant_id": str(tenant_id)},
        )


class InvalidPlanRequestError(RemediationPlannerError):
    """Raised when planning inputs fail structural or business validation."""


class UnsupportedDecisionForPlanningError(RemediationPlannerError):
    """Raised when a DecisionAction cannot produce an executable remediation plan."""
