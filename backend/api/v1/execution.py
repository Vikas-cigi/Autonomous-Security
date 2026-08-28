"""Execution Engine HTTP API."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import Field

from models.common import FortiBaseModel

from api.deps import dump, get_execution_container, map_engine_error, timed_call
from execution_engine.domain.inputs import ExecutionRequest
from execution_engine.query.filters import ExecutionSearchFilter
from execution_engine.query.pagination import PageRequest
from utils.response import error_response, success_response

router = APIRouter(prefix="/executions", tags=["Execution Engine"])


class CancelExecutionBody(FortiBaseModel):
    reason: str = Field(default="Cancelled by operator", max_length=2000)
    actor: Optional[str] = Field(default=None, max_length=256)


@router.post("")
def execute(body: ExecutionRequest):
    try:
        container = get_execution_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.engine.execute(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Execution completed",
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
def search_executions(
    tenant_id: UUID = Query(...),
    plan_id: Optional[UUID] = Query(None),
    finding_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    try:
        container = get_execution_container()
        with container.session() as session:
            svc = container.build(session)
            filters = ExecutionSearchFilter(
                tenant_id=tenant_id,
                plan_id=plan_id,
                finding_id=finding_id,
            )
            result, latency = timed_call(
                lambda: svc.engine.search(
                    filters, PageRequest(page=page, page_size=page_size)
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Executions search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/by-plan/{plan_id}")
def get_execution_for_plan(plan_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_execution_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.find_by_plan(plan_id, tenant_id)
            )
            return success_response(
                data=dump(result) if result else None,
                latency_ms=latency,
                message="Execution for plan",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.post("/{execution_id}/pause")
def pause_execution(execution_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_execution_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.pause(execution_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Execution paused",
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


@router.post("/{execution_id}/resume")
def resume_execution(execution_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_execution_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.resume(execution_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Execution resumed",
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


@router.post("/{execution_id}/cancel")
def cancel_execution(
    execution_id: UUID,
    body: CancelExecutionBody,
    tenant_id: UUID = Query(...),
):
    try:
        container = get_execution_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.cancel(
                    execution_id,
                    tenant_id,
                    reason=body.reason,
                    actor=body.actor,
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Execution cancelled",
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


@router.get("/{execution_id}/versions")
def list_execution_versions(execution_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_execution_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.list_versions(execution_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Execution versions",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/{execution_id}")
def get_execution(execution_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_execution_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.get(execution_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Execution retrieved",
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
