"""Enterprise Risk Engine exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class RiskEngineError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class RiskAssessmentNotFoundError(RiskEngineError):
    def __init__(self, assessment_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Risk assessment {assessment_id} not found for tenant {tenant_id}",
            details={
                "assessment_id": str(assessment_id),
                "tenant_id": str(tenant_id),
            },
        )


class RiskAssessmentForFindingNotFoundError(RiskEngineError):
    def __init__(self, finding_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"No risk assessment for finding {finding_id} in tenant {tenant_id}",
            details={
                "finding_id": str(finding_id),
                "tenant_id": str(tenant_id),
            },
        )


class TenantIsolationError(RiskEngineError):
    """Raised when a cross-tenant access attempt is detected."""


class InvalidRiskInputError(RiskEngineError):
    """Raised when risk scoring inputs fail structural or business validation."""
