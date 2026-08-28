"""Dependency injection container for Enterprise Reporting & Analytics."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from reporting_analytics.persistence.analytics_repository import (
    PostgresAnalyticsRepository,
)
from reporting_analytics.persistence.audit_reporting_repository import (
    PostgresAuditReportingRepository,
)
from reporting_analytics.persistence.dashboard_repository import (
    PostgresDashboardRepository,
)
from reporting_analytics.persistence.kpi_repository import PostgresKPIRepository
from reporting_analytics.persistence.report_history_repository import (
    PostgresReportHistoryRepository,
)
from reporting_analytics.persistence.reporting_repository import (
    PostgresReportingRepository,
)
from reporting_analytics.persistence.session import SessionFactory
from reporting_analytics.persistence.stores import ExportStore, ScheduleStore
from reporting_analytics.services.analytics_service import AnalyticsService
from reporting_analytics.services.audit_logger import AuditLogger
from reporting_analytics.services.dashboard_service import DashboardService
from reporting_analytics.services.export_service import ExportService
from reporting_analytics.services.kpi_service import KPIService
from reporting_analytics.services.report_scheduling_service import (
    ReportSchedulingService,
)
from reporting_analytics.services.reporting_service import ReportingService
from reporting_analytics.services.specialized_reports import (
    AuditReportingService,
    ComplianceReportingService,
    ExecutiveReportingService,
    OperationalReportingService,
    SpecializedReportBuilders,
)
from reporting_analytics.services.trend_analysis_service import TrendAnalysisService


@dataclass
class ReportingAnalyticsContainer:
    """
    Composition root for Reporting & Analytics Platform.

    Example::

        container = ReportingAnalyticsContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            report = svc.reporting.generate(request)
    """

    session_factory: SessionFactory

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> ReportingAnalyticsContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            )
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "ReportingAnalyticsServices":
        audit_logger = AuditLogger(session)
        reporting_repo = PostgresReportingRepository(
            session, audit_logger=audit_logger
        )
        dashboard_repo = PostgresDashboardRepository(
            session, audit_logger=audit_logger
        )
        analytics_repo = PostgresAnalyticsRepository(
            session, audit_logger=audit_logger
        )
        kpi_repo = PostgresKPIRepository(session)
        audit_repo = PostgresAuditReportingRepository(
            session, audit_logger=audit_logger
        )
        history_repo = PostgresReportHistoryRepository(session)
        schedule_store = ScheduleStore(session)
        export_store = ExportStore(session)

        kpi_service = KPIService()
        trend_service = TrendAnalysisService()
        analytics = AnalyticsService(
            analytics_repository=analytics_repo,
            kpi_repository=kpi_repo,
            audit_repository=audit_repo,
            kpi_service=kpi_service,
            trend_service=trend_service,
        )
        dashboard = DashboardService(
            dashboard_repository=dashboard_repo,
            analytics_service=analytics,
            audit_repository=audit_repo,
        )
        executive = ExecutiveReportingService(kpi_service)
        operational = OperationalReportingService(kpi_service)
        compliance = ComplianceReportingService()
        audit_reports = AuditReportingService()
        specialized = SpecializedReportBuilders()

        reporting = ReportingService(
            reporting_repository=reporting_repo,
            audit_repository=audit_repo,
            analytics_service=analytics,
            kpi_service=kpi_service,
            trend_service=trend_service,
            executive=executive,
            operational=operational,
            compliance=compliance,
            audit_reports=audit_reports,
            specialized=specialized,
        )
        export = ExportService(
            export_store=export_store,
            audit_repository=audit_repo,
        )
        scheduling = ReportSchedulingService(
            schedule_store=schedule_store,
            audit_repository=audit_repo,
            reporting_service=reporting,
        )

        return ReportingAnalyticsServices(
            audit_logger=audit_logger,
            reporting=reporting,
            dashboard=dashboard,
            analytics=analytics,
            kpi=kpi_service,
            trends=trend_service,
            export=export,
            scheduling=scheduling,
            executive=executive,
            operational=operational,
            compliance=compliance,
            audit_reports=audit_reports,
            reporting_repository=reporting_repo,
            dashboard_repository=dashboard_repo,
            analytics_repository=analytics_repo,
            kpi_repository=kpi_repo,
            audit_repository=audit_repo,
            history_repository=history_repo,
            schedule_store=schedule_store,
            export_store=export_store,
        )


@dataclass
class ReportingAnalyticsServices:
    """Bundled services sharing one unit-of-work session."""

    audit_logger: AuditLogger
    reporting: ReportingService
    dashboard: DashboardService
    analytics: AnalyticsService
    kpi: KPIService
    trends: TrendAnalysisService
    export: ExportService
    scheduling: ReportSchedulingService
    executive: ExecutiveReportingService
    operational: OperationalReportingService
    compliance: ComplianceReportingService
    audit_reports: AuditReportingService
    reporting_repository: PostgresReportingRepository
    dashboard_repository: PostgresDashboardRepository
    analytics_repository: PostgresAnalyticsRepository
    kpi_repository: PostgresKPIRepository
    audit_repository: PostgresAuditReportingRepository
    history_repository: PostgresReportHistoryRepository
    schedule_store: ScheduleStore
    export_store: ExportStore
