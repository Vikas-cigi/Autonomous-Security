"""
Enterprise Reporting & Analytics Platform.

Final Xolaris module: operational visibility, executive dashboards, compliance
reporting, remediation metrics, security posture analytics, AI operational
metrics, audit reporting, SLA tracking, and historical trend analysis.

Read-only. Never modifies platform data, executes remediation, invokes AI,
or recalculates trust/risk.
"""

from reporting_analytics.di.container import (
    ReportingAnalyticsContainer,
    ReportingAnalyticsServices,
)
from reporting_analytics.domain.enums import (
    DashboardType,
    ExportFormat,
    KPIName,
    ReportType,
    ScheduleCadence,
)
from reporting_analytics.domain.inputs import (
    PlatformAnalyticsInput,
    ReportGenerationRequest,
)
from reporting_analytics.domain.models import (
    AnalyticsSnapshot,
    Dashboard,
    ExportResult,
    KPI,
    Report,
    ReportResult,
)
from reporting_analytics.services.reporting_service import ReportingService

__all__ = [
    "AnalyticsSnapshot",
    "Dashboard",
    "DashboardType",
    "ExportFormat",
    "ExportResult",
    "KPI",
    "KPIName",
    "PlatformAnalyticsInput",
    "Report",
    "ReportGenerationRequest",
    "ReportResult",
    "ReportType",
    "ReportingAnalyticsContainer",
    "ReportingAnalyticsServices",
    "ReportingService",
    "ScheduleCadence",
]

__version__ = "1.0.0"
