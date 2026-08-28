"""Threat Intelligence Service exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class ThreatIntelligenceError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class ThreatIntelNotFoundError(ThreatIntelligenceError):
    def __init__(self, intel_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Threat intelligence {intel_id} not found for tenant {tenant_id}",
            details={"intel_id": str(intel_id), "tenant_id": str(tenant_id)},
        )


class CVENotFoundError(ThreatIntelligenceError):
    def __init__(self, cve_id: str, tenant_id: Optional[UUID] = None) -> None:
        super().__init__(
            f"CVE {cve_id} not found",
            details={"cve_id": cve_id, "tenant_id": str(tenant_id) if tenant_id else None},
        )


class IOCNotFoundError(ThreatIntelligenceError):
    def __init__(self, ioc_id: UUID, tenant_id: Optional[UUID] = None) -> None:
        super().__init__(
            f"IOC {ioc_id} not found",
            details={"ioc_id": str(ioc_id), "tenant_id": str(tenant_id) if tenant_id else None},
        )


class ThreatFeedNotFoundError(ThreatIntelligenceError):
    def __init__(self, feed_id: UUID) -> None:
        super().__init__(
            f"Threat feed {feed_id} not found",
            details={"feed_id": str(feed_id)},
        )


class ProviderNotImplementedError(ThreatIntelligenceError):
    """Raised by placeholder feed providers that have no live connector yet."""


class TenantIsolationError(ThreatIntelligenceError):
    """Raised when a cross-tenant access attempt is detected."""
