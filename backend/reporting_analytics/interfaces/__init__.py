"""Reporting & Analytics repository ports."""

from reporting_analytics.interfaces.analytics_repository import AnalyticsRepository
from reporting_analytics.interfaces.audit_reporting_repository import (
    AuditReportingRepository,
)
from reporting_analytics.interfaces.dashboard_repository import DashboardRepository
from reporting_analytics.interfaces.kpi_repository import KPIRepository
from reporting_analytics.interfaces.report_history_repository import (
    ReportHistoryRepository,
)
from reporting_analytics.interfaces.reporting_repository import ReportingRepository

__all__ = [
    "AnalyticsRepository",
    "AuditReportingRepository",
    "DashboardRepository",
    "KPIRepository",
    "ReportHistoryRepository",
    "ReportingRepository",
]
