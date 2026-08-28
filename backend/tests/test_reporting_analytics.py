"""Unit tests for Enterprise Reporting & Analytics Platform (SQLite)."""

from __future__ import annotations

import unittest
from datetime import timedelta
from uuid import uuid4

from models.common import utc_now

from reporting_analytics import (
    DashboardType,
    ExportFormat,
    PlatformAnalyticsInput,
    ReportGenerationRequest,
    ReportType,
    ReportingAnalyticsContainer,
    ScheduleCadence,
)
from reporting_analytics.domain.inputs import (
    ApprovalMetricsInput,
    AssetInventoryInput,
    ComplianceMetricsInput,
    DashboardAccessRequest,
    ExecutionMetricsInput,
    ExportGenerationRequest,
    FindingCountsInput,
    HistoricalSeriesInput,
    RemediationMetricsInput,
    RiskMetricsInput,
    ScheduleCreateRequest,
    TimeSeriesPointInput,
    TrustDistributionInput,
    VerificationMetricsInput,
)
from reporting_analytics.exceptions import (
    AccessDeniedError,
    InvalidReportingRequestError,
    ReportNotFoundError,
)
from reporting_analytics.query.filters import ReportSearchFilter
from reporting_analytics.query.pagination import PageRequest


def _snapshot(**overrides) -> PlatformAnalyticsInput:
    tenant_id = overrides.pop("tenant_id", uuid4())
    now = utc_now()
    data = {
        "tenant_id": tenant_id,
        "findings": FindingCountsInput(
            total=100, open=40, closed=60, critical=5, high=15, medium=30, low=50
        ),
        "assets": AssetInventoryInput(
            total_assets=200,
            covered_assets=180,
            critical_assets=20,
            environments={"prod": 100, "dev": 100},
        ),
        "trust": TrustDistributionInput(
            average_trust=0.72,
            low_trust_count=10,
            medium_trust_count=50,
            high_trust_count=140,
        ),
        "risk": RiskMetricsInput(
            average_risk=45.0,
            high_risk_count=20,
            critical_risk_count=5,
            pre_period_average_risk=60.0,
            post_period_average_risk=45.0,
        ),
        "remediation": RemediationMetricsInput(
            plans_created=30,
            plans_executed=25,
            mean_time_to_remediate_hours=18.0,
            mean_time_to_detect_hours=4.0,
        ),
        "approvals": ApprovalMetricsInput(
            total_approvals=40,
            approved_count=35,
            rejected_count=5,
            auto_approved_count=10,
            mean_approval_time_hours=6.0,
        ),
        "executions": ExecutionMetricsInput(
            total_executions=25,
            success_count=22,
            failure_count=3,
            rollback_count=1,
        ),
        "verifications": VerificationMetricsInput(
            total_verifications=22,
            verified_count=20,
            failed_count=1,
            reopened_count=1,
            escalated_count=0,
        ),
        "compliance": ComplianceMetricsInput(
            compliance_score=88.0,
            controls_passed=44,
            controls_failed=6,
            frameworks=["SOC2", "ISO27001"],
        ),
        "historical_series": [
            HistoricalSeriesInput(
                name="open_findings",
                points=[
                    TimeSeriesPointInput(timestamp=now - timedelta(days=7), value=55),
                    TimeSeriesPointInput(timestamp=now - timedelta(days=1), value=40),
                ],
            )
        ],
        "actor": "analyst",
        "evaluated_at": now,
    }
    data.update(overrides)
    return PlatformAnalyticsInput(**data)


class ReportingAnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = ReportingAnalyticsContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )

    def test_generate_executive_report(self) -> None:
        snap = _snapshot()
        with self.container.session() as session:
            svc = self.container.build(session)
            report = svc.reporting.generate(
                ReportGenerationRequest(
                    report_type=ReportType.EXECUTIVE.value,
                    snapshot=snap,
                    roles=["executive"],
                ),
                actor="ciso",
            )
            self.assertEqual(report.status.value, "completed")
            self.assertIsNotNone(report.result)
            self.assertIn("executive_summary", report.result.sections)
            self.assertGreater(len(report.result.kpis), 10)

            loaded = svc.reporting.get(report.id, report.tenant_id)
            self.assertEqual(loaded.id, report.id)

            page = svc.reporting.search(
                ReportSearchFilter(tenant_id=report.tenant_id),
                PageRequest(),
            )
            self.assertEqual(page.total_items, 1)

            versions = svc.reporting.list_versions(report.id, report.tenant_id)
            self.assertGreaterEqual(len(versions), 1)

    def test_dashboard_rbac(self) -> None:
        snap = _snapshot()
        with self.container.session() as session:
            svc = self.container.build(session)
            dash = svc.dashboard.build(
                DashboardAccessRequest(
                    dashboard_type=DashboardType.SOC.value,
                    snapshot=snap,
                    roles=["soc"],
                    actor="analyst",
                )
            )
            self.assertEqual(dash.dashboard_type, DashboardType.SOC)
            self.assertGreater(len(dash.widgets), 0)

            with self.assertRaises(AccessDeniedError):
                svc.dashboard.build(
                    DashboardAccessRequest(
                        dashboard_type=DashboardType.EXECUTIVE.value,
                        snapshot=snap,
                        roles=["analyst"],
                    )
                )

    def test_export_json_and_csv(self) -> None:
        snap = _snapshot()
        with self.container.session() as session:
            svc = self.container.build(session)
            report = svc.reporting.generate(
                ReportGenerationRequest(
                    report_type=ReportType.OPERATIONAL.value,
                    snapshot=snap,
                )
            )
            js = svc.export.export(
                ExportGenerationRequest(
                    format=ExportFormat.JSON.value,
                    report_id=report.id,
                    title="Ops Export",
                    actor="ops",
                ),
                report=report,
            )
            self.assertEqual(js.status.value, "completed")
            self.assertIn("Ops Export", js.content)

            csv_ex = svc.export.export(
                ExportGenerationRequest(
                    format=ExportFormat.CSV.value,
                    title="Ops CSV",
                    snapshot=snap,
                ),
            )
            self.assertIn("key,value", csv_ex.content)

    def test_schedule_and_run(self) -> None:
        snap = _snapshot()
        with self.container.session() as session:
            svc = self.container.build(session)
            schedule = svc.scheduling.create(
                ScheduleCreateRequest(
                    tenant_id=snap.tenant_id,
                    report_type=ReportType.COMPLIANCE.value,
                    cadence=ScheduleCadence.WEEKLY.value,
                    title="Weekly Compliance",
                    recipients=["compliance@xolaris.local"],
                    actor="admin",
                )
            )
            self.assertEqual(schedule.cadence, ScheduleCadence.WEEKLY)
            report = svc.scheduling.run_due(schedule, snap, actor="scheduler")
            self.assertEqual(report.report_type, ReportType.COMPLIANCE)
            self.assertIn("compliance", report.result.sections)

    def test_unknown_report_type(self) -> None:
        snap = _snapshot()
        with self.container.session() as session:
            svc = self.container.build(session)
            with self.assertRaises(InvalidReportingRequestError):
                svc.reporting.generate(
                    ReportGenerationRequest(
                        report_type="not_a_real_type",
                        snapshot=snap,
                    )
                )

    def test_report_not_found(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            with self.assertRaises(ReportNotFoundError):
                svc.reporting.get(uuid4(), uuid4())


if __name__ == "__main__":
    unittest.main()
