"""Decision Service HTTP API."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

from api.deps import (
    dump,
    get_decision_container,
    map_engine_error,
    timed_call,
    timed_call_async,
)
from decision_service.domain.inputs import DecisionRequest
from decision_service.query.filters import DecisionSearchFilter
from decision_service.query.pagination import PageRequest
from utils.response import error_response, success_response

router = APIRouter(prefix="/decisions", tags=["Decision Service"])


@router.post("")
async def decide(body: DecisionRequest):
    try:
        container = get_decision_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = await timed_call_async(
                lambda: svc.decision.decide(body)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Decision produced",
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
def search_decisions(
    tenant_id: UUID = Query(...),
    finding_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    try:
        container = get_decision_container()
        with container.session() as session:
            svc = container.build(session)
            filters = DecisionSearchFilter(tenant_id=tenant_id, finding_id=finding_id)
            result, latency = timed_call(
                lambda: svc.decision.search(
                    filters, PageRequest(page=page, page_size=page_size)
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Decisions search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/findings/{finding_id}")
def get_decision_for_finding(
    finding_id: UUID,
    tenant_id: UUID = Query(...),
):
    try:
        container = get_decision_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.decision.get_for_finding(finding_id, tenant_id)
            )
            return success_response(
                data=dump(result) if result else None,
                latency_ms=latency,
                message="Decision for finding",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/{decision_id}")
def get_decision(
    decision_id: UUID,
    tenant_id: UUID = Query(...),
):
    try:
        container = get_decision_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.decision.get_decision(decision_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Decision retrieved",
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
