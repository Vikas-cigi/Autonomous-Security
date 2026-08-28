"""Specialized report builders (executive, operational, compliance, audit)."""

from __future__ import annotations

from reporting_analytics.domain.inputs import PlatformAnalyticsInput
from reporting_analytics.domain.models import (
    AIUsageReport,
    AssetSecuritySummary,
    AuditReport,
    ComplianceReport,
    ExecutiveSummary,
    KPI,
    OperationalSummary,
    SecurityPostureReport,
    SLAReport,
    TenantAnalytics,
    ThreatIntelligenceSummary,
    UserActivityReport,
)
from reporting_analytics.services.kpi_service import KPIService, _rate


class ExecutiveReportingService:
    def __init__(self, kpi_service: KPIService | None = None) -> None:
        self._kpi = kpi_service or KPIService()

    def build(
        self, snapshot: PlatformAnalyticsInput, kpis: list[KPI] | None = None
    ) -> ExecutiveSummary:
        kpis = kpis or self._kpi.compute(snapshot)
        return ExecutiveSummary(
            headline="Executive security posture summary",
            key_points=[
                f"Open findings: {snapshot.findings.open}",
                f"Average risk: {snapshot.risk.average_risk:.1f}",
                f"Compliance score: {snapshot.compliance.compliance_score:.1f}",
                f"Verification success: {_rate(snapshot.verifications.verified_count, snapshot.verifications.total_verifications):.0%}",
            ],
            risk_outlook=(
                f"{snapshot.risk.critical_risk_count} critical and "
                f"{snapshot.risk.high_risk_count} high risk items remain."
            ),
            remediation_outlook=(
                f"MTTR {snapshot.remediation.mean_time_to_remediate_hours:.1f}h; "
                f"{snapshot.executions.success_count}/{snapshot.executions.total_executions} "
                "executions succeeded."
            ),
            kpis=kpis[:8],
        )


class OperationalReportingService:
    def __init__(self, kpi_service: KPIService | None = None) -> None:
        self._kpi = kpi_service or KPIService()

    def build(
        self, snapshot: PlatformAnalyticsInput, kpis: list[KPI] | None = None
    ) -> OperationalSummary:
        kpis = kpis or self._kpi.compute(snapshot)
        ver_rate = _rate(
            snapshot.verifications.verified_count,
            snapshot.verifications.total_verifications,
        )
        rollback = _rate(
            snapshot.executions.rollback_count, snapshot.executions.total_executions
        )
        bottlenecks: list[str] = []
        if snapshot.approvals.mean_approval_time_hours > 24:
            bottlenecks.append("Approval latency exceeds 24h")
        if rollback > 0.1:
            bottlenecks.append("Elevated rollback rate")
        if snapshot.findings.open > snapshot.findings.closed:
            bottlenecks.append("Open findings exceed closed")
        return OperationalSummary(
            headline="Operational remediation summary",
            open_findings=snapshot.findings.open,
            executions_in_period=snapshot.executions.total_executions,
            verification_success_rate=ver_rate,
            rollback_rate=rollback,
            bottlenecks=bottlenecks,
            kpis=kpis,
        )


class ComplianceReportingService:
    def build(self, snapshot: PlatformAnalyticsInput) -> ComplianceReport:
        gaps: list[str] = []
        if snapshot.compliance.controls_failed > 0:
            gaps.append(f"{snapshot.compliance.controls_failed} controls failed")
        if snapshot.compliance.compliance_score < 80:
            gaps.append("Compliance score below 80")
        return ComplianceReport(
            headline="Compliance report",
            compliance_score=snapshot.compliance.compliance_score,
            controls_passed=snapshot.compliance.controls_passed,
            controls_failed=snapshot.compliance.controls_failed,
            frameworks=list(snapshot.compliance.frameworks),
            gaps=gaps,
        )


class AuditReportingService:
    def build(self, snapshot: PlatformAnalyticsInput) -> AuditReport:
        return AuditReport(
            headline="Control-plane audit report",
            total_events_referenced=(
                snapshot.approvals.total_approvals
                + snapshot.executions.total_executions
                + snapshot.verifications.total_verifications
            ),
            approvals=snapshot.approvals.total_approvals,
            executions=snapshot.executions.total_executions,
            verifications=snapshot.verifications.total_verifications,
            notes=[
                "Derived from platform analytics snapshots only.",
                "Source module data was not modified.",
            ],
        )


class SpecializedReportBuilders:
    """Convenience builders for remaining report section types."""

    def security_posture(self, snapshot: PlatformAnalyticsInput) -> SecurityPostureReport:
        coverage = _rate(snapshot.assets.covered_assets, snapshot.assets.total_assets)
        posture = max(
            0.0,
            min(
                100.0,
                (
                    (100.0 - snapshot.risk.average_risk) * 0.4
                    + snapshot.trust.average_trust * 100.0 * 0.3
                    + snapshot.compliance.compliance_score * 0.3
                ),
            ),
        )
        recs: list[str] = []
        if snapshot.findings.critical > 0:
            recs.append("Prioritize critical open findings")
        if coverage < 0.8:
            recs.append("Improve asset coverage")
        return SecurityPostureReport(
            headline="Security posture report",
            posture_score=posture,
            critical_open=snapshot.findings.critical,
            high_open=snapshot.findings.high,
            asset_coverage=coverage,
            trust_average=snapshot.trust.average_trust,
            risk_average=snapshot.risk.average_risk,
            recommendations=recs,
        )

    def assets(self, snapshot: PlatformAnalyticsInput) -> AssetSecuritySummary:
        return AssetSecuritySummary(
            total_assets=snapshot.assets.total_assets,
            covered_assets=snapshot.assets.covered_assets,
            critical_assets=snapshot.assets.critical_assets,
            coverage_ratio=_rate(
                snapshot.assets.covered_assets, snapshot.assets.total_assets
            ),
            environments=dict(snapshot.assets.environments),
        )

    def threat_intel(self, snapshot: PlatformAnalyticsInput) -> ThreatIntelligenceSummary:
        return ThreatIntelligenceSummary(
            total_indicators=snapshot.threat_intel.total_indicators,
            active_threats=snapshot.threat_intel.active_threats,
            cves_tracked=snapshot.threat_intel.cves_tracked,
            feed_health_ratio=snapshot.threat_intel.feed_health_ratio,
        )

    def sla(self, snapshot: PlatformAnalyticsInput) -> SLAReport:
        ratio = _rate(
            snapshot.sla.within_sla_count,
            snapshot.sla.within_sla_count + snapshot.sla.breached_count,
        )
        return SLAReport(
            headline="SLA compliance report",
            sla_compliance_ratio=ratio,
            within_sla=snapshot.sla.within_sla_count,
            breached=snapshot.sla.breached_count,
            target_hours=snapshot.sla.sla_target_hours,
        )

    def ai_usage(self, snapshot: PlatformAnalyticsInput) -> AIUsageReport:
        return AIUsageReport(
            headline="AI usage report",
            total_invocations=snapshot.ai_usage.total_invocations,
            success_rate=_rate(
                snapshot.ai_usage.success_count, snapshot.ai_usage.total_invocations
            ),
            total_tokens=snapshot.ai_usage.total_tokens,
            average_latency_ms=snapshot.ai_usage.average_latency_ms,
        )

    def tenant(self, snapshot: PlatformAnalyticsInput, kpis: list[KPI]) -> TenantAnalytics:
        return TenantAnalytics(
            tenant_id=snapshot.tenant_id,
            kpis=kpis,
            findings_total=snapshot.findings.total,
            risk_average=snapshot.risk.average_risk,
            trust_average=snapshot.trust.average_trust,
            utilization=min(
                1.0,
                (
                    snapshot.executions.total_executions
                    + snapshot.verifications.total_verifications
                )
                / 50.0,
            ),
        )

    def user_activity(
        self,
        *,
        report_generations: int = 0,
        dashboard_accesses: int = 0,
        exports: int = 0,
        actors: list[str] | None = None,
    ) -> UserActivityReport:
        return UserActivityReport(
            headline="User activity report",
            report_generations=report_generations,
            dashboard_accesses=dashboard_accesses,
            exports=exports,
            actors=list(actors or []),
        )
