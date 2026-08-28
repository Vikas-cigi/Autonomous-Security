"""Dashboard framework — RBAC-aware, read-only widgets from KPIs."""

from __future__ import annotations

from typing import List, Optional

from models.common import new_id, utc_now
from reporting_analytics.domain.enums import (
    AuditAction,
    DashboardType,
    KPIName,
    WidgetType,
)
from reporting_analytics.domain.history import ReportingAuditRecord
from reporting_analytics.domain.inputs import DashboardAccessRequest
from reporting_analytics.domain.models import Dashboard, DashboardWidget, KPI
from reporting_analytics.exceptions import AccessDeniedError, InvalidReportingRequestError
from reporting_analytics.interfaces.audit_reporting_repository import (
    AuditReportingRepository,
)
from reporting_analytics.interfaces.dashboard_repository import DashboardRepository
from reporting_analytics.services.analytics_service import AnalyticsService

# Role gates for sensitive dashboards (empty list = any authenticated tenant role)
DASHBOARD_ROLES: dict[DashboardType, List[str]] = {
    DashboardType.EXECUTIVE: ["executive", "ciso", "admin"],
    DashboardType.SOC: ["soc", "analyst", "admin"],
    DashboardType.SECURITY_OPERATIONS: ["soc", "ops", "admin"],
    DashboardType.COMPLIANCE: ["compliance", "auditor", "admin"],
    DashboardType.INFRASTRUCTURE: ["infra", "ops", "admin"],
    DashboardType.RISK: ["risk", "ciso", "admin"],
    DashboardType.THREAT: ["threat", "soc", "admin"],
    DashboardType.ASSET: ["asset", "ops", "admin"],
    DashboardType.AI_OPERATIONS: ["ai_ops", "admin"],
    DashboardType.PLATFORM_HEALTH: ["admin", "platform"],
}


class DashboardService:
    def __init__(
        self,
        dashboard_repository: Optional[DashboardRepository] = None,
        analytics_service: Optional[AnalyticsService] = None,
        audit_repository: Optional[AuditReportingRepository] = None,
    ) -> None:
        self._repo = dashboard_repository
        self._analytics = analytics_service or AnalyticsService()
        self._audit = audit_repository

    def build(
        self,
        request: DashboardAccessRequest,
        *,
        persist: bool = True,
    ) -> Dashboard:
        try:
            dtype = DashboardType(request.dashboard_type)
        except ValueError as exc:
            raise InvalidReportingRequestError(
                f"Unknown dashboard type: {request.dashboard_type}",
                details={"dashboard_type": request.dashboard_type},
            ) from exc

        self._ensure_access(dtype, request.roles)
        snap = self._analytics.build_snapshot(
            request.snapshot, persist=persist, label=f"dashboard:{dtype.value}"
        )
        widgets = self._widgets_for(dtype, snap.kpis)
        dashboard = Dashboard(
            id=new_id(),
            tenant_id=request.snapshot.tenant_id,
            dashboard_type=dtype,
            title=f"{dtype.value.replace('_', ' ').title()} Dashboard",
            widgets=widgets,
            kpis=snap.kpis,
            roles_allowed=list(DASHBOARD_ROLES.get(dtype, [])),
            generated_at=utc_now(),
            generated_by=request.actor or request.snapshot.actor,
        )
        if persist and self._repo is not None:
            dashboard = self._repo.save(dashboard, actor=request.actor)
        if self._audit is not None:
            self._audit.append(
                ReportingAuditRecord(
                    tenant_id=dashboard.tenant_id,
                    dashboard_id=dashboard.id,
                    action=AuditAction.DASHBOARD_ACCESSED,
                    actor=request.actor,
                    message=f"Dashboard accessed: {dtype.value}",
                    status="ok",
                )
            )
        return dashboard

    def _ensure_access(self, dtype: DashboardType, roles: List[str]) -> None:
        required = DASHBOARD_ROLES.get(dtype, [])
        if not required:
            return
        role_set = {r.lower() for r in roles}
        if "admin" in role_set:
            return
        if not role_set.intersection({r.lower() for r in required}):
            raise AccessDeniedError(
                f"Insufficient roles for dashboard {dtype.value}",
                details={"required": required, "provided": roles},
            )

    def _widgets_for(
        self, dtype: DashboardType, kpis: List[KPI]
    ) -> List[DashboardWidget]:
        by_name = {k.name: k for k in kpis}
        catalog: dict[DashboardType, List[KPIName]] = {
            DashboardType.EXECUTIVE: [
                KPIName.OPEN_FINDINGS,
                KPIName.RISK_REDUCTION,
                KPIName.COMPLIANCE_SCORE,
                KPIName.SLA_COMPLIANCE,
            ],
            DashboardType.SOC: [
                KPIName.OPEN_FINDINGS,
                KPIName.VERIFICATION_SUCCESS_RATE,
                KPIName.EXECUTION_SUCCESS_RATE,
                KPIName.ROLLBACK_RATE,
            ],
            DashboardType.SECURITY_OPERATIONS: [
                KPIName.MTTR_HOURS,
                KPIName.MTTD_HOURS,
                KPIName.APPROVAL_TIME_HOURS,
                KPIName.AUTO_APPROVAL_RATE,
            ],
            DashboardType.COMPLIANCE: [
                KPIName.COMPLIANCE_SCORE,
                KPIName.SLA_COMPLIANCE,
                KPIName.CLOSED_FINDINGS,
            ],
            DashboardType.INFRASTRUCTURE: [
                KPIName.ASSET_COVERAGE,
                KPIName.PLATFORM_UTILIZATION,
                KPIName.ROLLBACK_RATE,
            ],
            DashboardType.RISK: [
                KPIName.RISK_REDUCTION,
                KPIName.VULNERABILITY_TREND,
                KPIName.OPEN_FINDINGS,
            ],
            DashboardType.THREAT: [
                KPIName.VULNERABILITY_TREND,
                KPIName.OPEN_FINDINGS,
                KPIName.TRUST_DISTRIBUTION,
            ],
            DashboardType.ASSET: [
                KPIName.ASSET_COVERAGE,
                KPIName.TRUST_DISTRIBUTION,
                KPIName.TOTAL_FINDINGS,
            ],
            DashboardType.AI_OPERATIONS: [
                KPIName.AI_USAGE,
                KPIName.PLATFORM_UTILIZATION,
            ],
            DashboardType.PLATFORM_HEALTH: [
                KPIName.PLATFORM_UTILIZATION,
                KPIName.EXECUTION_SUCCESS_RATE,
                KPIName.VERIFICATION_SUCCESS_RATE,
                KPIName.MULTI_TENANT_METRICS,
            ],
        }
        names = catalog.get(dtype, [KPIName.OPEN_FINDINGS])
        widgets: List[DashboardWidget] = []
        for i, name in enumerate(names):
            kpi = by_name.get(name)
            if kpi is None:
                continue
            widgets.append(
                DashboardWidget(
                    widget_type=WidgetType.KPI,
                    title=kpi.label,
                    kpi_name=name,
                    metrics=[],
                    position=i,
                )
            )
        widgets.append(
            DashboardWidget(
                widget_type=WidgetType.SUMMARY,
                title="Summary",
                position=len(widgets),
                config={"kpi_count": str(len(kpis))},
            )
        )
        return widgets
