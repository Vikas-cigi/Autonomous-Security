"""Analytics snapshot assembly."""

from __future__ import annotations

from typing import List, Optional

from models.common import new_id
from reporting_analytics.domain.enums import AuditAction
from reporting_analytics.domain.inputs import PlatformAnalyticsInput
from reporting_analytics.domain.models import AnalyticsSnapshot, Metric
from reporting_analytics.interfaces.analytics_repository import AnalyticsRepository
from reporting_analytics.interfaces.kpi_repository import KPIRepository
from reporting_analytics.services.kpi_service import KPIService
from reporting_analytics.services.trend_analysis_service import TrendAnalysisService
from reporting_analytics.domain.history import ReportingAuditRecord
from reporting_analytics.interfaces.audit_reporting_repository import (
    AuditReportingRepository,
)


class AnalyticsService:
    def __init__(
        self,
        analytics_repository: Optional[AnalyticsRepository] = None,
        kpi_repository: Optional[KPIRepository] = None,
        audit_repository: Optional[AuditReportingRepository] = None,
        kpi_service: Optional[KPIService] = None,
        trend_service: Optional[TrendAnalysisService] = None,
    ) -> None:
        self._analytics = analytics_repository
        self._kpis = kpi_repository
        self._audit = audit_repository
        self._kpi_svc = kpi_service or KPIService()
        self._trends = trend_service or TrendAnalysisService()

    def build_snapshot(
        self,
        input_data: PlatformAnalyticsInput,
        *,
        persist: bool = True,
        label: str = "snapshot",
    ) -> AnalyticsSnapshot:
        kpis = self._kpi_svc.compute(input_data)
        trends = self._trends.analyze_all(input_data)
        series = [t.series for t in trends if t.series is not None]
        metrics = [
            Metric(name="average_risk", value=input_data.risk.average_risk, unit="score"),
            Metric(
                name="average_trust",
                value=input_data.trust.average_trust,
                unit="score",
            ),
            Metric(
                name="compliance_score",
                value=input_data.compliance.compliance_score,
                unit="score",
            ),
        ]
        raw = {
            "findings_total": float(input_data.findings.total),
            "findings_open": float(input_data.findings.open),
            "executions": float(input_data.executions.total_executions),
            "verifications": float(input_data.verifications.total_verifications),
            "assets": float(input_data.assets.total_assets),
        }
        snapshot = AnalyticsSnapshot(
            id=new_id(),
            tenant_id=input_data.tenant_id,
            label=label,
            kpis=kpis,
            metrics=metrics,
            trends=trends,
            series=series,
            raw_counts=raw,
            period_start=input_data.period_start,
            period_end=input_data.period_end,
        )
        if persist and self._analytics is not None:
            snapshot = self._analytics.save(snapshot)
            if self._kpis is not None:
                self._kpis.save_many(snapshot.tenant_id, snapshot.id, kpis)
            if self._audit is not None:
                self._audit.append(
                    ReportingAuditRecord(
                        tenant_id=snapshot.tenant_id,
                        action=AuditAction.SNAPSHOT_STORED,
                        actor=input_data.actor,
                        message="Analytics snapshot built",
                        details={"snapshot_id": str(snapshot.id)},
                    )
                )
        return snapshot
