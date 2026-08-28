"""Remediation Planner HTTP API."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

from api.deps import dump, get_planner_container, map_engine_error, timed_call
from remediation_planner.domain.inputs import RemediationPlanRequest
from remediation_planner.query.filters import RemediationPlanSearchFilter
from remediation_planner.query.pagination import PageRequest
from utils.response import error_response, success_response

router = APIRouter(prefix="/remediation-plans", tags=["Remediation Planner"])


@router.post("")
def create_plan(body: RemediationPlanRequest):
    try:
        container = get_planner_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.planner.plan(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Remediation plan created",
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


@router.get("")
def search_plans(
    tenant_id: UUID = Query(...),
    finding_id: Optional[UUID] = Query(None),
    decision_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    try:
        container = get_planner_container()
        with container.session() as session:
            svc = container.build(session)
            filters = RemediationPlanSearchFilter(
                tenant_id=tenant_id,
                finding_id=finding_id,
                decision_id=decision_id,
            )
            result, latency = timed_call(
                lambda: svc.planner.search(
                    filters, PageRequest(page=page, page_size=page_size)
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Remediation plans search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/by-decision/{decision_id}")
def get_plan_for_decision(decision_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_planner_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.planner.get_for_decision(decision_id, tenant_id)
            )
            return success_response(
                data=dump(result) if result else None,
                latency_ms=latency,
                message="Remediation plan for decision",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/{plan_id}")
def get_plan(plan_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_planner_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.planner.get_plan(plan_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Remediation plan retrieved",
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
