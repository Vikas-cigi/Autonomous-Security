"""Report scheduling framework (cadence metadata + deterministic execution hooks)."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from models.common import new_id, utc_now
from reporting_analytics.domain.enums import (
    AuditAction,
    ReportType,
    ScheduleCadence,
)
from reporting_analytics.domain.history import ReportingAuditRecord
from reporting_analytics.domain.inputs import (
    PlatformAnalyticsInput,
    ReportGenerationRequest,
    ScheduleCreateRequest,
)
from reporting_analytics.domain.models import Report, ReportSchedule
from reporting_analytics.exceptions import InvalidReportingRequestError
from reporting_analytics.interfaces.audit_reporting_repository import (
    AuditReportingRepository,
)
from reporting_analytics.persistence.stores import ScheduleStore


CADENCE_DELTAS = {
    ScheduleCadence.DAILY: timedelta(days=1),
    ScheduleCadence.WEEKLY: timedelta(weeks=1),
    ScheduleCadence.MONTHLY: timedelta(days=30),
    ScheduleCadence.QUARTERLY: timedelta(days=90),
    ScheduleCadence.YEARLY: timedelta(days=365),
    ScheduleCadence.MANUAL: None,
    ScheduleCadence.EVENT_TRIGGERED: None,
}


class ReportSchedulingService:
    """
    Manage schedules and trigger report generation.

    Does not send email; callers handle delivery using schedule.recipients.
    """

    def __init__(
        self,
        schedule_store: Optional[ScheduleStore] = None,
        audit_repository: Optional[AuditReportingRepository] = None,
        reporting_service: Optional[object] = None,
    ) -> None:
        self._store = schedule_store
        self._audit = audit_repository
        self._reporting = reporting_service

    def create(self, request: ScheduleCreateRequest) -> ReportSchedule:
        try:
            rtype = ReportType(request.report_type)
            cadence = ScheduleCadence(request.cadence)
        except ValueError as exc:
            raise InvalidReportingRequestError(
                "Invalid schedule report_type or cadence",
                details={
                    "report_type": request.report_type,
                    "cadence": request.cadence,
                },
            ) from exc

        now = utc_now()
        delta = CADENCE_DELTAS.get(cadence)
        schedule = ReportSchedule(
            id=new_id(),
            tenant_id=request.tenant_id,
            report_type=rtype,
            cadence=cadence,
            title=request.title,
            template_id=request.template_id,
            recipients=list(request.recipients),
            enabled=request.enabled,
            last_run_at=None,
            next_run_at=now + delta if delta else None,
            created_by=request.actor,
        )
        if self._store is not None:
            schedule = self._store.save(schedule)
        if self._audit is not None:
            self._audit.append(
                ReportingAuditRecord(
                    tenant_id=schedule.tenant_id,
                    schedule_id=schedule.id,
                    action=AuditAction.SCHEDULE_CREATED,
                    actor=request.actor,
                    message=f"Schedule created: {cadence.value}",
                    status="enabled" if schedule.enabled else "disabled",
                )
            )
        return schedule

    def run_due(
        self,
        schedule: ReportSchedule,
        snapshot: PlatformAnalyticsInput,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> Report:
        if self._reporting is None:
            raise InvalidReportingRequestError(
                "ReportingService not wired into ReportSchedulingService"
            )
        if schedule.tenant_id != snapshot.tenant_id:
            raise InvalidReportingRequestError(
                "Schedule tenant_id must match snapshot tenant_id"
            )

        try:
            report = self._reporting.generate(  # type: ignore[attr-defined]
                ReportGenerationRequest(
                    report_type=schedule.report_type.value,
                    title=schedule.title,
                    template_id=schedule.template_id,
                    snapshot=snapshot,
                ),
                persist=persist,
                actor=actor or schedule.created_by,
            )
            schedule.last_run_at = utc_now()
            delta = CADENCE_DELTAS.get(schedule.cadence)
            schedule.next_run_at = (
                schedule.last_run_at + delta if delta else schedule.next_run_at
            )
            if self._store is not None:
                schedule = self._store.save(schedule)
            if self._audit is not None:
                self._audit.append(
                    ReportingAuditRecord(
                        tenant_id=schedule.tenant_id,
                        schedule_id=schedule.id,
                        report_id=report.id,
                        action=AuditAction.SCHEDULE_EXECUTED,
                        actor=actor,
                        message="Scheduled report executed",
                        status=report.status.value,
                    )
                )
            return report
        except Exception as exc:
            if self._audit is not None:
                self._audit.append(
                    ReportingAuditRecord(
                        tenant_id=schedule.tenant_id,
                        schedule_id=schedule.id,
                        action=AuditAction.SCHEDULE_FAILED,
                        actor=actor,
                        message=str(exc)[:4000],
                        status="failed",
                    )
                )
            raise
