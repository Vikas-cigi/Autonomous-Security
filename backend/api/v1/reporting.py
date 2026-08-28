"""Reporting & Analytics HTTP API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from api.deps import dump, get_reporting_container, map_engine_error, timed_call
from reporting_analytics.domain.inputs import (
    DashboardAccessRequest,
    ExportGenerationRequest,
    PlatformAnalyticsInput,
    ReportGenerationRequest,
    ScheduleCreateRequest,
)
from reporting_analytics.query.filters import ReportSearchFilter
from reporting_analytics.query.pagination import PageRequest
from utils.response import error_response, success_response

router = APIRouter(prefix="/reporting", tags=["Reporting & Analytics"])


@router.post("/reports")
def generate_report(body: ReportGenerationRequest):
    try:
        container = get_reporting_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.reporting.generate(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Report generated",
            )
    except Exception as exc:
        http_exc = map_engine_error(exc)
        if http_exc.status_code < 500:
            return error_response(
                code=http_exc.detail["code"],
                details=http_exc.detail.get("details") or http_exc.detail["message"],
                message=http_exc.detail["message"],
            )
        raise http_exc from exc


@router.get("/reports")
def search_reports(
    tenant_id: UUID = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    try:
        container = get_reporting_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.reporting.search(
                    ReportSearchFilter(tenant_id=tenant_id),
                    PageRequest(page=page, page_size=page_size),
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Reports search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/reports/{report_id}")
def get_report(report_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_reporting_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.reporting.get(report_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Report retrieved",
            )
    except Exception as exc:
        http_exc = map_engine_error(exc)
        if http_exc.status_code == 404:
            return error_response(
                code=http_exc.detail["code"],
                details=http_exc.detail.get("details"),
                message=http_exc.detail["message"],
            )
        raise http_exc from exc


@router.post("/dashboards")
def build_dashboard(body: DashboardAccessRequest):
    try:
        container = get_reporting_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.dashboard.build(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Dashboard built",
            )
    except Exception as exc:
        http_exc = map_engine_error(exc)
        if http_exc.status_code < 500:
            return error_response(
                code=http_exc.detail["code"],
                details=http_exc.detail.get("details") or http_exc.detail["message"],
                message=http_exc.detail["message"],
            )
        raise http_exc from exc


@router.post("/analytics/snapshots")
def build_analytics_snapshot(body: PlatformAnalyticsInput):
    try:
        container = get_reporting_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.analytics.build_snapshot(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Analytics snapshot stored",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.post("/exports")
def create_export(body: ExportGenerationRequest):
    try:
        container = get_reporting_container()
        with container.session() as session:
            svc = container.build(session)
            report = None
            if body.report_id is not None:
                if body.snapshot is None:
                    return error_response(
                        code="InvalidReportingRequestError",
                        details={"report_id": str(body.report_id)},
                        message=(
                            "Exporting an existing report requires snapshot "
                            "for tenant context"
                        ),
                    )
                report = svc.reporting.get(body.report_id, body.snapshot.tenant_id)
            result, latency = timed_call(
                lambda: svc.export.export(body, report=report)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Export created",
            )
    except Exception as exc:
        http_exc = map_engine_error(exc)
        if http_exc.status_code < 500:
            return error_response(
                code=http_exc.detail["code"],
                details=http_exc.detail.get("details") or http_exc.detail["message"],
                message=http_exc.detail["message"],
            )
        raise http_exc from exc


@router.post("/schedules")
def create_schedule(body: ScheduleCreateRequest):
    try:
        container = get_reporting_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.scheduling.create(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Report schedule created",
            )
    except Exception as exc:
        http_exc = map_engine_error(exc)
        if http_exc.status_code < 500:
            return error_response(
                code=http_exc.detail["code"],
                details=http_exc.detail.get("details") or http_exc.detail["message"],
                message=http_exc.detail["message"],
            )
        raise http_exc from exc
