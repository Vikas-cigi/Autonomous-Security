"""
Read-only platform snapshots for Reporting & Analytics.

Callers assemble these from upstream modules. This package never queries
or mutates source systems.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, utc_now


class FindingCountsInput(FortiBaseModel):
    total: int = Field(default=0, ge=0)
    open: int = Field(default=0, ge=0)
    closed: int = Field(default=0, ge=0)
    critical: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    low: int = Field(default=0, ge=0)


class AssetInventoryInput(FortiBaseModel):
    total_assets: int = Field(default=0, ge=0)
    covered_assets: int = Field(default=0, ge=0)
    critical_assets: int = Field(default=0, ge=0)
    environments: Dict[str, int] = Field(default_factory=dict)


class ThreatIntelInput(FortiBaseModel):
    total_indicators: int = Field(default=0, ge=0)
    active_threats: int = Field(default=0, ge=0)
    cves_tracked: int = Field(default=0, ge=0)
    feed_health_ratio: float = Field(default=1.0, ge=0.0, le=1.0)


class TrustDistributionInput(FortiBaseModel):
    average_trust: float = Field(default=0.5, ge=0.0, le=1.0)
    low_trust_count: int = Field(default=0, ge=0)
    medium_trust_count: int = Field(default=0, ge=0)
    high_trust_count: int = Field(default=0, ge=0)


class RiskMetricsInput(FortiBaseModel):
    average_risk: float = Field(default=0.0, ge=0.0, le=100.0)
    high_risk_count: int = Field(default=0, ge=0)
    critical_risk_count: int = Field(default=0, ge=0)
    pre_period_average_risk: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    post_period_average_risk: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class DecisionMetricsInput(FortiBaseModel):
    total_decisions: int = Field(default=0, ge=0)
    remediate_count: int = Field(default=0, ge=0)
    monitor_count: int = Field(default=0, ge=0)
    suppress_count: int = Field(default=0, ge=0)
    mean_decision_latency_hours: float = Field(default=0.0, ge=0.0)


class AIUsageInput(FortiBaseModel):
    total_invocations: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    average_latency_ms: float = Field(default=0.0, ge=0.0)


class RemediationMetricsInput(FortiBaseModel):
    plans_created: int = Field(default=0, ge=0)
    plans_executed: int = Field(default=0, ge=0)
    mean_time_to_remediate_hours: float = Field(default=0.0, ge=0.0)
    mean_time_to_detect_hours: float = Field(default=0.0, ge=0.0)


class SimulationMetricsInput(FortiBaseModel):
    total_simulations: int = Field(default=0, ge=0)
    safe_to_execute_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)


class ApprovalMetricsInput(FortiBaseModel):
    total_approvals: int = Field(default=0, ge=0)
    approved_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    auto_approved_count: int = Field(default=0, ge=0)
    mean_approval_time_hours: float = Field(default=0.0, ge=0.0)


class ExecutionMetricsInput(FortiBaseModel):
    total_executions: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    rollback_count: int = Field(default=0, ge=0)


class VerificationMetricsInput(FortiBaseModel):
    total_verifications: int = Field(default=0, ge=0)
    verified_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    reopened_count: int = Field(default=0, ge=0)
    escalated_count: int = Field(default=0, ge=0)


class EvidenceMetricsInput(FortiBaseModel):
    total_evidence: int = Field(default=0, ge=0)
    linked_to_findings: int = Field(default=0, ge=0)


class ComplianceMetricsInput(FortiBaseModel):
    compliance_score: float = Field(default=0.0, ge=0.0, le=100.0)
    controls_passed: int = Field(default=0, ge=0)
    controls_failed: int = Field(default=0, ge=0)
    frameworks: List[str] = Field(default_factory=list)


class SLAMetricsInput(FortiBaseModel):
    sla_target_hours: float = Field(default=72.0, ge=0.0)
    within_sla_count: int = Field(default=0, ge=0)
    breached_count: int = Field(default=0, ge=0)


class TimeSeriesPointInput(FortiBaseModel):
    timestamp: datetime = Field(...)
    value: float = Field(...)
    label: Optional[str] = Field(default=None, max_length=128)

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class HistoricalSeriesInput(FortiBaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    points: List[TimeSeriesPointInput] = Field(default_factory=list)


class PlatformAnalyticsInput(FortiBaseModel):
    """Complete read-only snapshot for analytics / report generation."""

    tenant_id: UUID = Field(...)
    findings: FindingCountsInput = Field(default_factory=FindingCountsInput)
    assets: AssetInventoryInput = Field(default_factory=AssetInventoryInput)
    threat_intel: ThreatIntelInput = Field(default_factory=ThreatIntelInput)
    trust: TrustDistributionInput = Field(default_factory=TrustDistributionInput)
    risk: RiskMetricsInput = Field(default_factory=RiskMetricsInput)
    decisions: DecisionMetricsInput = Field(default_factory=DecisionMetricsInput)
    ai_usage: AIUsageInput = Field(default_factory=AIUsageInput)
    remediation: RemediationMetricsInput = Field(default_factory=RemediationMetricsInput)
    simulation: SimulationMetricsInput = Field(default_factory=SimulationMetricsInput)
    approvals: ApprovalMetricsInput = Field(default_factory=ApprovalMetricsInput)
    executions: ExecutionMetricsInput = Field(default_factory=ExecutionMetricsInput)
    verifications: VerificationMetricsInput = Field(
        default_factory=VerificationMetricsInput
    )
    evidence: EvidenceMetricsInput = Field(default_factory=EvidenceMetricsInput)
    compliance: ComplianceMetricsInput = Field(default_factory=ComplianceMetricsInput)
    sla: SLAMetricsInput = Field(default_factory=SLAMetricsInput)
    historical_series: List[HistoricalSeriesInput] = Field(default_factory=list)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    actor: Optional[str] = Field(default=None, max_length=256)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("period_start", "period_end", "evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ReportGenerationRequest(FortiBaseModel):
    report_type: str = Field(..., min_length=1, max_length=64)
    title: Optional[str] = Field(default=None, max_length=256)
    template_id: Optional[UUID] = None
    snapshot: PlatformAnalyticsInput = Field(...)
    roles: List[str] = Field(default_factory=list)
    include_trends: bool = Field(default=True)


class DashboardAccessRequest(FortiBaseModel):
    dashboard_type: str = Field(..., min_length=1, max_length=64)
    snapshot: PlatformAnalyticsInput = Field(...)
    roles: List[str] = Field(default_factory=list)
    actor: Optional[str] = Field(default=None, max_length=256)


class ExportGenerationRequest(FortiBaseModel):
    format: str = Field(..., min_length=1, max_length=16)
    report_id: Optional[UUID] = None
    dashboard_id: Optional[UUID] = None
    snapshot: Optional[PlatformAnalyticsInput] = None
    title: str = Field(default="Xolaris Export", max_length=256)
    actor: Optional[str] = Field(default=None, max_length=256)


class ScheduleCreateRequest(FortiBaseModel):
    tenant_id: UUID = Field(...)
    report_type: str = Field(..., min_length=1, max_length=64)
    cadence: str = Field(..., min_length=1, max_length=32)
    template_id: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=256)
    recipients: List[str] = Field(default_factory=list)
    enabled: bool = Field(default=True)
    actor: Optional[str] = Field(default=None, max_length=256)
