"""Domain enums for Enterprise Reporting & Analytics Platform."""

from __future__ import annotations

from enum import Enum


class ReportType(str, Enum):
    EXECUTIVE = "executive"
    OPERATIONAL = "operational"
    SECURITY_POSTURE = "security_posture"
    COMPLIANCE = "compliance"
    AUDIT = "audit"
    ASSET = "asset"
    THREAT_INTELLIGENCE = "threat_intelligence"
    RISK = "risk"
    TRUST = "trust"
    REMEDIATION = "remediation"
    APPROVAL = "approval"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    AI_USAGE = "ai_usage"
    SLA = "sla"
    TENANT = "tenant"


class DashboardType(str, Enum):
    EXECUTIVE = "executive"
    SOC = "soc"
    SECURITY_OPERATIONS = "security_operations"
    COMPLIANCE = "compliance"
    INFRASTRUCTURE = "infrastructure"
    RISK = "risk"
    THREAT = "threat"
    ASSET = "asset"
    AI_OPERATIONS = "ai_operations"
    PLATFORM_HEALTH = "platform_health"


class WidgetType(str, Enum):
    KPI = "kpi"
    TIMESERIES = "timeseries"
    TABLE = "table"
    DISTRIBUTION = "distribution"
    TREND = "trend"
    SUMMARY = "summary"


class KPIName(str, Enum):
    TOTAL_FINDINGS = "total_findings"
    OPEN_FINDINGS = "open_findings"
    CLOSED_FINDINGS = "closed_findings"
    MTTR_HOURS = "mttr_hours"
    MTTD_HOURS = "mttd_hours"
    APPROVAL_TIME_HOURS = "approval_time_hours"
    EXECUTION_SUCCESS_RATE = "execution_success_rate"
    VERIFICATION_SUCCESS_RATE = "verification_success_rate"
    AUTO_APPROVAL_RATE = "auto_approval_rate"
    ROLLBACK_RATE = "rollback_rate"
    COMPLIANCE_SCORE = "compliance_score"
    RISK_REDUCTION = "risk_reduction"
    TRUST_DISTRIBUTION = "trust_distribution"
    ASSET_COVERAGE = "asset_coverage"
    VULNERABILITY_TREND = "vulnerability_trend"
    SLA_COMPLIANCE = "sla_compliance"
    AI_USAGE = "ai_usage"
    PLATFORM_UTILIZATION = "platform_utilization"
    MULTI_TENANT_METRICS = "multi_tenant_metrics"


class ScheduleCadence(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    MANUAL = "manual"
    EVENT_TRIGGERED = "event_triggered"


class ReportStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExportFormat(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class ExportStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


class AuditAction(str, Enum):
    REPORT_GENERATED = "report_generated"
    REPORT_FAILED = "report_failed"
    DASHBOARD_ACCESSED = "dashboard_accessed"
    EXPORT_CREATED = "export_created"
    EXPORT_FAILED = "export_failed"
    SCHEDULE_CREATED = "schedule_created"
    SCHEDULE_EXECUTED = "schedule_executed"
    SCHEDULE_FAILED = "schedule_failed"
    KPI_COMPUTED = "kpi_computed"
    SNAPSHOT_STORED = "snapshot_stored"
    SEARCHED = "searched"
    HISTORY_RECORDED = "history_recorded"
