"""Core domain models for Enterprise Reporting & Analytics Platform."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from reporting_analytics.domain.enums import (
    DashboardType,
    ExportFormat,
    ExportStatus,
    KPIName,
    ReportStatus,
    ReportType,
    ScheduleCadence,
    TrendDirection,
    WidgetType,
)

ALGORITHM_VERSION = "1.0.0"


class Metric(FortiBaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    value: float = Field(...)
    unit: Optional[str] = Field(default=None, max_length=32)
    metadata: Dict[str, str] = Field(default_factory=dict)


class KPI(FortiBaseModel):
    kpi_id: UUID = Field(default_factory=new_id)
    name: KPIName = Field(...)
    label: str = Field(..., min_length=1, max_length=256)
    value: float = Field(...)
    unit: Optional[str] = Field(default=None, max_length=32)
    target: Optional[float] = None
    trend: TrendDirection = Field(default=TrendDirection.UNKNOWN)
    period_label: Optional[str] = Field(default=None, max_length=64)
    metadata: Dict[str, str] = Field(default_factory=dict)


class TimeSeriesMetric(FortiBaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    points: List[Metric] = Field(default_factory=list)
    timestamps: List[datetime] = Field(default_factory=list)
    values: List[float] = Field(default_factory=list)

    @field_validator("timestamps", mode="before")
    @classmethod
    def ensure_tz_list(cls, value: object) -> object:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, datetime) and item.tzinfo is None:
                    raise ValueError("timestamps must be timezone-aware")
        return value


class TrendAnalysis(FortiBaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    direction: TrendDirection = Field(...)
    change_ratio: float = Field(default=0.0)
    current_value: float = Field(...)
    previous_value: Optional[float] = None
    explanation: str = Field(..., min_length=1, max_length=2000)
    series: Optional[TimeSeriesMetric] = None


class RiskTrend(TrendAnalysis):
    pass


class TrustTrend(TrendAnalysis):
    pass


class RemediationTrend(TrendAnalysis):
    pass


class DashboardWidget(FortiBaseModel):
    widget_id: UUID = Field(default_factory=new_id)
    widget_type: WidgetType = Field(...)
    title: str = Field(..., min_length=1, max_length=256)
    kpi_name: Optional[KPIName] = None
    metrics: List[Metric] = Field(default_factory=list)
    series: Optional[TimeSeriesMetric] = None
    position: int = Field(default=0, ge=0)
    config: Dict[str, str] = Field(default_factory=dict)


class Dashboard(TimestampedModel):
    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    dashboard_type: DashboardType = Field(...)
    title: str = Field(..., min_length=1, max_length=256)
    widgets: List[DashboardWidget] = Field(default_factory=list)
    kpis: List[KPI] = Field(default_factory=list)
    roles_allowed: List[str] = Field(default_factory=list)
    algorithm_version: str = Field(default=ALGORITHM_VERSION, max_length=32)
    generated_at: datetime = Field(default_factory=utc_now)
    generated_by: Optional[str] = Field(default=None, max_length=256)

    @field_validator("generated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ReportTemplate(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    tenant_id: Optional[UUID] = None
    report_type: ReportType = Field(...)
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)
    sections: List[str] = Field(default_factory=list)
    default_export_format: ExportFormat = Field(default=ExportFormat.JSON)
    version: int = Field(default=1, ge=1)


class ReportSchedule(TimestampedModel):
    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    report_type: ReportType = Field(...)
    cadence: ScheduleCadence = Field(...)
    title: str = Field(..., min_length=1, max_length=256)
    template_id: Optional[UUID] = None
    recipients: List[str] = Field(default_factory=list)
    enabled: bool = Field(default=True)
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_by: Optional[str] = Field(default=None, max_length=256)

    @field_validator("last_run_at", "next_run_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ReportResult(FortiBaseModel):
    summary: str = Field(..., min_length=1, max_length=8000)
    kpis: List[KPI] = Field(default_factory=list)
    metrics: List[Metric] = Field(default_factory=list)
    trends: List[TrendAnalysis] = Field(default_factory=list)
    sections: Dict[str, Any] = Field(default_factory=dict)


class ReportExecution(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    report_id: UUID = Field(...)
    status: ReportStatus = Field(...)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = Field(default=None, max_length=4000)
    actor: Optional[str] = Field(default=None, max_length=256)

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class Report(TimestampedModel):
    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    report_type: ReportType = Field(...)
    title: str = Field(..., min_length=1, max_length=256)
    status: ReportStatus = Field(default=ReportStatus.PENDING)
    template_id: Optional[UUID] = None
    result: Optional[ReportResult] = None
    execution: Optional[ReportExecution] = None
    roles_allowed: List[str] = Field(default_factory=list)
    algorithm_version: str = Field(default=ALGORITHM_VERSION, max_length=32)
    current_version: int = Field(default=1, ge=1)
    generated_at: Optional[datetime] = None
    generated_by: Optional[str] = Field(default=None, max_length=256)

    @field_validator("generated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class AnalyticsSnapshot(TimestampedModel):
    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    label: str = Field(default="snapshot", max_length=128)
    kpis: List[KPI] = Field(default_factory=list)
    metrics: List[Metric] = Field(default_factory=list)
    trends: List[TrendAnalysis] = Field(default_factory=list)
    series: List[TimeSeriesMetric] = Field(default_factory=list)
    raw_counts: Dict[str, float] = Field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    algorithm_version: str = Field(default=ALGORITHM_VERSION, max_length=32)

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ExecutiveSummary(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    key_points: List[str] = Field(default_factory=list)
    risk_outlook: str = Field(..., min_length=1, max_length=2000)
    remediation_outlook: str = Field(..., min_length=1, max_length=2000)
    kpis: List[KPI] = Field(default_factory=list)


class OperationalSummary(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    open_findings: int = Field(default=0, ge=0)
    executions_in_period: int = Field(default=0, ge=0)
    verification_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    rollback_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    bottlenecks: List[str] = Field(default_factory=list)
    kpis: List[KPI] = Field(default_factory=list)


class SecurityPostureReport(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    posture_score: float = Field(..., ge=0.0, le=100.0)
    critical_open: int = Field(default=0, ge=0)
    high_open: int = Field(default=0, ge=0)
    asset_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    trust_average: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_average: float = Field(default=0.0, ge=0.0, le=100.0)
    recommendations: List[str] = Field(default_factory=list)


class ComplianceReport(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    compliance_score: float = Field(..., ge=0.0, le=100.0)
    controls_passed: int = Field(default=0, ge=0)
    controls_failed: int = Field(default=0, ge=0)
    frameworks: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)


class AuditReport(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    total_events_referenced: int = Field(default=0, ge=0)
    approvals: int = Field(default=0, ge=0)
    executions: int = Field(default=0, ge=0)
    verifications: int = Field(default=0, ge=0)
    notes: List[str] = Field(default_factory=list)


class AssetSecuritySummary(FortiBaseModel):
    total_assets: int = Field(default=0, ge=0)
    covered_assets: int = Field(default=0, ge=0)
    critical_assets: int = Field(default=0, ge=0)
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    environments: Dict[str, int] = Field(default_factory=dict)


class ThreatIntelligenceSummary(FortiBaseModel):
    total_indicators: int = Field(default=0, ge=0)
    active_threats: int = Field(default=0, ge=0)
    cves_tracked: int = Field(default=0, ge=0)
    feed_health_ratio: float = Field(default=1.0, ge=0.0, le=1.0)


class SLAReport(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    sla_compliance_ratio: float = Field(..., ge=0.0, le=1.0)
    within_sla: int = Field(default=0, ge=0)
    breached: int = Field(default=0, ge=0)
    target_hours: float = Field(default=72.0, ge=0.0)


class AIUsageReport(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    total_invocations: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    total_tokens: int = Field(default=0, ge=0)
    average_latency_ms: float = Field(default=0.0, ge=0.0)


class UserActivityReport(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    report_generations: int = Field(default=0, ge=0)
    dashboard_accesses: int = Field(default=0, ge=0)
    exports: int = Field(default=0, ge=0)
    actors: List[str] = Field(default_factory=list)


class TenantAnalytics(FortiBaseModel):
    tenant_id: UUID = Field(...)
    kpis: List[KPI] = Field(default_factory=list)
    findings_total: int = Field(default=0, ge=0)
    risk_average: float = Field(default=0.0, ge=0.0, le=100.0)
    trust_average: float = Field(default=0.0, ge=0.0, le=1.0)
    utilization: float = Field(default=0.0, ge=0.0, le=1.0)


class ExportRequest(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    format: ExportFormat = Field(...)
    title: str = Field(..., min_length=1, max_length=256)
    report_id: Optional[UUID] = None
    dashboard_id: Optional[UUID] = None
    actor: Optional[str] = Field(default=None, max_length=256)
    requested_at: datetime = Field(default_factory=utc_now)

    @field_validator("requested_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ExportResult(TimestampedModel):
    id: UUID = Field(default_factory=new_id)
    request_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    format: ExportFormat = Field(...)
    status: ExportStatus = Field(...)
    title: str = Field(..., min_length=1, max_length=256)
    content_type: str = Field(..., min_length=1, max_length=128)
    # Deterministic serialized payload (never binary PDF rendering in-core)
    content: str = Field(..., min_length=0)
    byte_length: int = Field(default=0, ge=0)
    error_message: Optional[str] = Field(default=None, max_length=4000)
    completed_at: Optional[datetime] = None

    @field_validator("completed_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value
