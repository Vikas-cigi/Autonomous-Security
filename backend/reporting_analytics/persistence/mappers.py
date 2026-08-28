"""Map between Reporting & Analytics domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from reporting_analytics.domain.enums import AuditAction
from reporting_analytics.domain.history import ReportHistory, ReportingAuditRecord
from reporting_analytics.domain.models import (
    AnalyticsSnapshot,
    Dashboard,
    ExportResult,
    KPI,
    Report,
    ReportSchedule,
)
from reporting_analytics.persistence.orm import (
    AnalyticsSnapshotORM,
    DashboardORM,
    ExportResultORM,
    KPIRecordORM,
    ReportORM,
    ReportScheduleORM,
    ReportVersionORM,
    ReportingAuditORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def report_to_orm(report: Report, *, version: int) -> ReportORM:
    return ReportORM(
        id=report.id,
        tenant_id=report.tenant_id,
        report_type=report.report_type.value,
        title=report.title,
        status=report.status.value,
        algorithm_version=report.algorithm_version,
        current_version=version,
        payload=report.model_dump(mode="json"),
        generated_at=report.generated_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def apply_report_to_orm(row: ReportORM, report: Report, *, version: int) -> None:
    row.report_type = report.report_type.value
    row.title = report.title
    row.status = report.status.value
    row.algorithm_version = report.algorithm_version
    row.current_version = version
    row.payload = report.model_dump(mode="json")
    row.generated_at = report.generated_at
    row.updated_at = report.updated_at


def orm_to_report(row: ReportORM) -> Report:
    return Report.model_validate(row.payload)


def version_from_orm(row: ReportVersionORM) -> ReportHistory:
    return ReportHistory(
        id=row.id,
        report_id=row.report_id,
        tenant_id=row.tenant_id,
        version=row.version,
        snapshot=Report.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def dashboard_to_orm(dashboard: Dashboard) -> DashboardORM:
    return DashboardORM(
        id=dashboard.id,
        tenant_id=dashboard.tenant_id,
        dashboard_type=dashboard.dashboard_type.value,
        title=dashboard.title,
        payload=dashboard.model_dump(mode="json"),
        generated_at=dashboard.generated_at,
        created_at=dashboard.created_at,
        updated_at=dashboard.updated_at,
    )


def apply_dashboard_to_orm(row: DashboardORM, dashboard: Dashboard) -> None:
    row.dashboard_type = dashboard.dashboard_type.value
    row.title = dashboard.title
    row.payload = dashboard.model_dump(mode="json")
    row.generated_at = dashboard.generated_at
    row.updated_at = dashboard.updated_at


def orm_to_dashboard(row: DashboardORM) -> Dashboard:
    return Dashboard.model_validate(row.payload)


def snapshot_to_orm(snapshot: AnalyticsSnapshot) -> AnalyticsSnapshotORM:
    return AnalyticsSnapshotORM(
        id=snapshot.id,
        tenant_id=snapshot.tenant_id,
        label=snapshot.label,
        payload=snapshot.model_dump(mode="json"),
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def orm_to_snapshot(row: AnalyticsSnapshotORM) -> AnalyticsSnapshot:
    return AnalyticsSnapshot.model_validate(row.payload)


def kpi_to_orm(kpi: KPI, *, tenant_id, snapshot_id) -> KPIRecordORM:
    return KPIRecordORM(
        tenant_id=tenant_id,
        snapshot_id=snapshot_id,
        kpi_id=kpi.kpi_id,
        name=kpi.name.value,
        label=kpi.label,
        value=kpi.value,
        unit=kpi.unit,
        trend=kpi.trend.value,
        payload=kpi.model_dump(mode="json"),
    )


def orm_to_kpi(row: KPIRecordORM) -> KPI:
    return KPI.model_validate(row.payload)


def schedule_to_orm(schedule: ReportSchedule) -> ReportScheduleORM:
    return ReportScheduleORM(
        id=schedule.id,
        tenant_id=schedule.tenant_id,
        report_type=schedule.report_type.value,
        cadence=schedule.cadence.value,
        title=schedule.title,
        enabled=schedule.enabled,
        payload=schedule.model_dump(mode="json"),
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def apply_schedule_to_orm(row: ReportScheduleORM, schedule: ReportSchedule) -> None:
    row.report_type = schedule.report_type.value
    row.cadence = schedule.cadence.value
    row.title = schedule.title
    row.enabled = schedule.enabled
    row.payload = schedule.model_dump(mode="json")
    row.last_run_at = schedule.last_run_at
    row.next_run_at = schedule.next_run_at
    row.updated_at = schedule.updated_at


def orm_to_schedule(row: ReportScheduleORM) -> ReportSchedule:
    return ReportSchedule.model_validate(row.payload)


def export_to_orm(result: ExportResult) -> ExportResultORM:
    return ExportResultORM(
        id=result.id,
        tenant_id=result.tenant_id,
        request_id=result.request_id,
        format=result.format.value,
        status=result.status.value,
        title=result.title,
        payload=result.model_dump(mode="json"),
        created_at=result.created_at,
        updated_at=result.updated_at,
    )


def orm_to_export(row: ExportResultORM) -> ExportResult:
    return ExportResult.model_validate(row.payload)


def audit_from_orm(row: ReportingAuditORM) -> ReportingAuditRecord:
    return ReportingAuditRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        report_id=row.report_id,
        dashboard_id=row.dashboard_id,
        export_id=row.export_id,
        schedule_id=row.schedule_id,
        action=AuditAction(row.action),
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        status=row.status,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


def audit_to_orm(record: ReportingAuditRecord) -> ReportingAuditORM:
    return ReportingAuditORM(
        id=record.id,
        tenant_id=record.tenant_id,
        report_id=record.report_id,
        dashboard_id=record.dashboard_id,
        export_id=record.export_id,
        schedule_id=record.schedule_id,
        action=record.action.value,
        actor=record.actor,
        message=record.message,
        status=record.status,
        details=record.details,
        created_at=record.created_at,
    )
