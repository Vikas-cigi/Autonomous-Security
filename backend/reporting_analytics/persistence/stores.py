"""Schedule + export persistence helpers (local to reporting platform)."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from reporting_analytics.domain.models import ExportResult, ReportSchedule
from reporting_analytics.persistence.mappers import (
    apply_schedule_to_orm,
    export_to_orm,
    orm_to_export,
    orm_to_schedule,
    schedule_to_orm,
)
from reporting_analytics.persistence.orm import ExportResultORM, ReportScheduleORM


class ScheduleStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, schedule: ReportSchedule) -> ReportSchedule:
        row = self._session.get(ReportScheduleORM, schedule.id)
        if row is None:
            schedule.touch()
            row = schedule_to_orm(schedule)
            self._session.add(row)
        else:
            schedule.touch()
            apply_schedule_to_orm(row, schedule)
        self._session.flush()
        return orm_to_schedule(row)

    def get(self, schedule_id: UUID, tenant_id: UUID) -> Optional[ReportSchedule]:
        row = self._session.get(ReportScheduleORM, schedule_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return orm_to_schedule(row)

    def list_enabled(self, tenant_id: UUID) -> List[ReportSchedule]:
        stmt = select(ReportScheduleORM).where(
            ReportScheduleORM.tenant_id == tenant_id,
            ReportScheduleORM.enabled.is_(True),
        )
        return [orm_to_schedule(r) for r in self._session.scalars(stmt).all()]


class ExportStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, result: ExportResult) -> ExportResult:
        result.touch()
        row = self._session.get(ExportResultORM, result.id)
        if row is None:
            row = export_to_orm(result)
            self._session.add(row)
        else:
            row.status = result.status.value
            row.payload = result.model_dump(mode="json")
            row.updated_at = result.updated_at
        self._session.flush()
        return orm_to_export(row)

    def get(self, export_id: UUID, tenant_id: UUID) -> Optional[ExportResult]:
        row = self._session.get(ExportResultORM, export_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return orm_to_export(row)
