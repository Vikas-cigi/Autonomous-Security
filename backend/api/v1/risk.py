"""Risk Engine HTTP API."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

from api.deps import dump, get_risk_container, map_engine_error, timed_call
from risk_engine.domain.inputs import RiskScoringInput
from risk_engine.query.filters import RiskAssessmentSearchFilter
from risk_engine.query.pagination import PageRequest
from utils.response import error_response, success_response

router = APIRouter(prefix="/risk", tags=["Risk Engine"])


@router.post("/score")
def score_risk(body: RiskScoringInput):
    try:
        container = get_risk_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.risk_engine.score(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Risk assessment scored",
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


@router.get("/assessments/{assessment_id}")
def get_risk_assessment(
    assessment_id: UUID,
    tenant_id: UUID = Query(...),
):
    try:
        container = get_risk_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.risk_engine.get_assessment(assessment_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Risk assessment retrieved",
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


@router.get("/findings/{finding_id}")
def get_risk_for_finding(
    finding_id: UUID,
    tenant_id: UUID = Query(...),
):
    try:
        container = get_risk_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.risk_engine.get_for_finding(finding_id, tenant_id)
            )
            return success_response(
                data=dump(result) if result else None,
                latency_ms=latency,
                message="Risk assessment for finding",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/assessments")
def search_risk_assessments(
    tenant_id: UUID = Query(...),
    finding_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    try:
        container = get_risk_container()
        with container.session() as session:
            svc = container.build(session)
            filters = RiskAssessmentSearchFilter(
                tenant_id=tenant_id, finding_id=finding_id
            )
            result, latency = timed_call(
                lambda: svc.risk_engine.search(
                    filters, PageRequest(page=page, page_size=page_size)
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Risk assessments search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc
