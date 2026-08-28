"""Evidence Repository exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class EvidenceRepositoryError(Exception):
    """Base error for the Evidence Repository."""

    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class FindingNotFoundError(EvidenceRepositoryError):
    """Raised when a finding cannot be located for the tenant."""

    def __init__(self, finding_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Finding {finding_id} not found for tenant {tenant_id}",
            details={"finding_id": str(finding_id), "tenant_id": str(tenant_id)},
        )
        self.finding_id = finding_id
        self.tenant_id = tenant_id


class EvidenceNotFoundError(EvidenceRepositoryError):
    """Raised when evidence cannot be located for the tenant."""

    def __init__(self, evidence_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Evidence {evidence_id} not found for tenant {tenant_id}",
            details={"evidence_id": str(evidence_id), "tenant_id": str(tenant_id)},
        )


class TenantIsolationError(EvidenceRepositoryError):
    """Raised when a cross-tenant access attempt is detected."""


class ConcurrentModificationError(EvidenceRepositoryError):
    """Raised when optimistic version checks fail."""
