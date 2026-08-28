"""ReportingService — facade for enterprise report generation."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from models.common import new_id, utc_now
from reporting_analytics.domain.enums import (
    AuditAction,
    ReportStatus,
    ReportType,
)
from reporting_analytics.domain.history import ReportingAuditRecord
from reporting_analytics.domain.inputs import ReportGenerationRequest
from reporting_analytics.domain.models import (
    Report,
    ReportExecution,
    ReportResult,
    ReportTemplate,
)
from reporting_analytics.exceptions import InvalidReportingRequestError
from reporting_analytics.interfaces.audit_reporting_repository import (
    AuditReportingRepository,
)
from reporting_analytics.interfaces.reporting_repository import ReportingRepository
from reporting_analytics.query.filters import ReportSearchFilter
from reporting_analytics.query.pagination import Page, PageRequest
from reporting_analytics.services.analytics_service import AnalyticsService
from reporting_analytics.services.kpi_service import KPIService
from reporting_analytics.services.specialized_reports import (
    AuditReportingService,
    ComplianceReportingService,
    ExecutiveReportingService,
    OperationalReportingService,
    SpecializedReportBuilders,
)
from reporting_analytics.services.trend_analysis_service import TrendAnalysisService

DEFAULT_TEMPLATES: dict[ReportType, list[str]] = {
    ReportType.EXECUTIVE: ["executive_summary", "kpis", "risk_outlook"],
    ReportType.OPERATIONAL: ["operational_summary", "bottlenecks", "kpis"],
    ReportType.SECURITY_POSTURE: ["posture", "recommendations"],
    ReportType.COMPLIANCE: ["compliance", "gaps"],
    ReportType.AUDIT: ["audit_trail"],
    ReportType.ASSET: ["assets"],
    ReportType.THREAT_INTELLIGENCE: ["threat_intel"],
    ReportType.RISK: ["risk_trends", "kpis"],
    ReportType.TRUST: ["trust_distribution"],
    ReportType.REMEDIATION: ["remediation_metrics"],
    ReportType.APPROVAL: ["approval_metrics"],
    ReportType.EXECUTION: ["execution_metrics"],
    ReportType.VERIFICATION: ["verification_metrics"],
    ReportType.AI_USAGE: ["ai_usage"],
    ReportType.SLA: ["sla"],
    ReportType.TENANT: ["tenant_analytics"],
}


class ReportingService:
    """
    Generate enterprise reports from read-only platform snapshots.

    Never modifies source modules, executes remediation, invokes AI,
    or recalculates trust/risk.
    """

    def __init__(
        self,
        reporting_repository: Optional[ReportingRepository] = None,
        audit_repository: Optional[AuditReportingRepository] = None,
        analytics_service: Optional[AnalyticsService] = None,
        kpi_service: Optional[KPIService] = None,
        trend_service: Optional[TrendAnalysisService] = None,
        executive: Optional[ExecutiveReportingService] = None,
        operational: Optional[OperationalReportingService] = None,
        compliance: Optional[ComplianceReportingService] = None,
        audit_reports: Optional[AuditReportingService] = None,
        specialized: Optional[SpecializedReportBuilders] = None,
    ) -> None:
        self._repo = reporting_repository
        self._audit = audit_repository
        self._analytics = analytics_service or AnalyticsService()
        self._kpi = kpi_service or KPIService()
        self._trends = trend_service or TrendAnalysisService()
        self._executive = executive or ExecutiveReportingService(self._kpi)
        self._operational = operational or OperationalReportingService(self._kpi)
        self._compliance = compliance or ComplianceReportingService()
        self._audit_reports = audit_reports or AuditReportingService()
        self._specialized = specialized or SpecializedReportBuilders()

    def generate(
        self,
        request: ReportGenerationRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        report_id: Optional[UUID] = None,
    ) -> Report:
        try:
            rtype = ReportType(request.report_type)
        except ValueError as exc:
            raise InvalidReportingRequestError(
                f"Unknown report type: {request.report_type}",
                details={"report_type": request.report_type},
            ) from exc

        started = utc_now()
        rid = report_id or new_id()
        execution = ReportExecution(
            report_id=rid,
            status=ReportStatus.RUNNING,
            started_at=started,
            actor=actor or request.snapshot.actor,
        )
        report = Report(
            id=rid,
            tenant_id=request.snapshot.tenant_id,
            report_type=rtype,
            title=request.title
            or f"{rtype.value.replace('_', ' ').title()} Report",
            status=ReportStatus.RUNNING,
            template_id=request.template_id,
            execution=execution,
            roles_allowed=list(request.roles),
            generated_by=actor or request.snapshot.actor,
        )

        try:
            kpis = self._kpi.compute(request.snapshot)
            trends = (
                self._trends.analyze_all(request.snapshot)
                if request.include_trends
                else []
            )
            sections = self._build_sections(rtype, request, kpis)
            summary = self._headline(rtype, sections)
            result = ReportResult(
                summary=summary,
                kpis=kpis,
                metrics=[],
                trends=trends,
                sections=sections,
            )
            completed = utc_now()
            report.result = result
            report.status = ReportStatus.COMPLETED
            report.generated_at = completed
            report.execution = ReportExecution(
                id=execution.id,
                report_id=rid,
                status=ReportStatus.COMPLETED,
                started_at=started,
                completed_at=completed,
                actor=execution.actor,
            )
            action = AuditAction.REPORT_GENERATED
        except Exception as exc:  # noqa: BLE001
            report.status = ReportStatus.FAILED
            report.execution = ReportExecution(
                id=execution.id,
                report_id=rid,
                status=ReportStatus.FAILED,
                started_at=started,
                completed_at=utc_now(),
                error_message=str(exc)[:4000],
                actor=execution.actor,
            )
            action = AuditAction.REPORT_FAILED
            if persist and self._repo is not None:
                self._repo.save(
                    report,
                    actor=actor,
                    change_summary=f"Report failed: {exc}",
                )
            if self._audit is not None:
                self._audit.append(
                    ReportingAuditRecord(
                        tenant_id=report.tenant_id,
                        report_id=report.id,
                        action=action,
                        actor=actor,
                        message=str(exc)[:4000],
                        status="failed",
                    )
                )
            raise

        if persist and self._repo is not None:
            report = self._repo.save(
                report,
                actor=actor,
                change_summary=f"Report generated: {rtype.value}",
            )
        if self._audit is not None:
            self._audit.append(
                ReportingAuditRecord(
                    tenant_id=report.tenant_id,
                    report_id=report.id,
                    action=action,
                    actor=actor,
                    message=f"Report generated: {rtype.value}",
                    status=report.status.value,
                )
            )
        # Also store analytics snapshot for historical KPI tracking
        self._analytics.build_snapshot(
            request.snapshot,
            persist=persist,
            label=f"report:{rtype.value}",
        )
        return report

    def get(self, report_id: UUID, tenant_id: UUID) -> Report:
        if self._repo is None:
            raise InvalidReportingRequestError("ReportingRepository not configured")
        return self._repo.get(report_id, tenant_id)

    def search(
        self,
        filters: ReportSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[Report]:
        if self._repo is None:
            raise InvalidReportingRequestError("ReportingRepository not configured")
        return self._repo.search(filters, page or PageRequest())

    def list_versions(self, report_id: UUID, tenant_id: UUID):
        if self._repo is None:
            raise InvalidReportingRequestError("ReportingRepository not configured")
        return self._repo.list_versions(report_id, tenant_id)

    def default_template(self, report_type: ReportType) -> ReportTemplate:
        return ReportTemplate(
            report_type=report_type,
            name=f"{report_type.value} template",
            description=f"Default template for {report_type.value} reports",
            sections=list(DEFAULT_TEMPLATES.get(report_type, ["summary"])),
        )

    def _build_sections(
        self,
        rtype: ReportType,
        request: ReportGenerationRequest,
        kpis,
    ) -> dict:
        snap = request.snapshot
        sections: dict = {"kpis": [k.model_dump(mode="json") for k in kpis]}
        if rtype == ReportType.EXECUTIVE:
            sections["executive_summary"] = self._executive.build(
                snap, kpis
            ).model_dump(mode="json")
        elif rtype == ReportType.OPERATIONAL:
            sections["operational_summary"] = self._operational.build(
                snap, kpis
            ).model_dump(mode="json")
        elif rtype == ReportType.COMPLIANCE:
            sections["compliance"] = self._compliance.build(snap).model_dump(
                mode="json"
            )
        elif rtype == ReportType.AUDIT:
            sections["audit"] = self._audit_reports.build(snap).model_dump(mode="json")
        elif rtype == ReportType.SECURITY_POSTURE:
            sections["security_posture"] = self._specialized.security_posture(
                snap
            ).model_dump(mode="json")
        elif rtype == ReportType.ASSET:
            sections["assets"] = self._specialized.assets(snap).model_dump(mode="json")
        elif rtype == ReportType.THREAT_INTELLIGENCE:
            sections["threat_intel"] = self._specialized.threat_intel(snap).model_dump(
                mode="json"
            )
        elif rtype == ReportType.SLA:
            sections["sla"] = self._specialized.sla(snap).model_dump(mode="json")
        elif rtype == ReportType.AI_USAGE:
            sections["ai_usage"] = self._specialized.ai_usage(snap).model_dump(
                mode="json"
            )
        elif rtype == ReportType.TENANT:
            sections["tenant"] = self._specialized.tenant(snap, kpis).model_dump(
                mode="json"
            )
        elif rtype == ReportType.RISK:
            sections["risk"] = snap.risk.model_dump(mode="json")
        elif rtype == ReportType.TRUST:
            sections["trust"] = snap.trust.model_dump(mode="json")
        elif rtype == ReportType.REMEDIATION:
            sections["remediation"] = snap.remediation.model_dump(mode="json")
        elif rtype == ReportType.APPROVAL:
            sections["approvals"] = snap.approvals.model_dump(mode="json")
        elif rtype == ReportType.EXECUTION:
            sections["executions"] = snap.executions.model_dump(mode="json")
        elif rtype == ReportType.VERIFICATION:
            sections["verifications"] = snap.verifications.model_dump(mode="json")
        return sections

    @staticmethod
    def _headline(rtype: ReportType, sections: dict) -> str:
        return (
            f"{rtype.value.replace('_', ' ').title()} report generated with "
            f"{len(sections)} sections."
        )
