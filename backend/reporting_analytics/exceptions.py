"""Reporting & Analytics exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class ReportingAnalyticsError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class ReportNotFoundError(ReportingAnalyticsError):
    def __init__(self, report_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Report {report_id} not found for tenant {tenant_id}",
            details={"report_id": str(report_id), "tenant_id": str(tenant_id)},
        )


class DashboardNotFoundError(ReportingAnalyticsError):
    def __init__(self, dashboard_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Dashboard {dashboard_id} not found for tenant {tenant_id}",
            details={"dashboard_id": str(dashboard_id), "tenant_id": str(tenant_id)},
        )


class InvalidReportingRequestError(ReportingAnalyticsError):
    """Raised when reporting inputs fail structural validation."""


class AccessDeniedError(ReportingAnalyticsError):
    """Raised when RBAC roles are insufficient for a dashboard/report."""


class ExportError(ReportingAnalyticsError):
    """Raised when export serialization fails."""
