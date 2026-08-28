"""Approval Engine HTTP API."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import Field

from models.common import FortiBaseModel

from api.deps import dump, get_approval_container, map_engine_error, timed_call
from approval_engine.domain.inputs import (
    ApprovalSubmitRequest,
    DelegateApprovalRequest,
    EscalateApprovalRequest,
    RecordDecisionRequest,
)
from approval_engine.query.filters import ApprovalSearchFilter
from approval_engine.query.pagination import PageRequest
from utils.response import error_response, success_response

router = APIRouter(prefix="/approvals", tags=["Approval Engine"])


class CancelApprovalBody(FortiBaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)
    actor: Optional[str] = Field(default=None, max_length=256)


class CommentBody(FortiBaseModel):
    author: str = Field(..., min_length=1, max_length=256)
    body: str = Field(..., min_length=1, max_length=4000)


@router.post("")
def submit_approval(body: ApprovalSubmitRequest):
    try:
        container = get_approval_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.engine.submit(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Approval request submitted",
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


@router.post("/decisions")
def record_decision(body: RecordDecisionRequest):
    try:
        container = get_approval_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.engine.record_decision(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Approval decision recorded",
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


@router.post("/escalate")
def escalate_approval(body: EscalateApprovalRequest):
    try:
        container = get_approval_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.engine.escalate(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Approval escalated",
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


@router.post("/delegate")
def delegate_approval(body: DelegateApprovalRequest):
    try:
        container = get_approval_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.engine.delegate(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Approval delegated",
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
def search_approvals(
    tenant_id: UUID = Query(...),
    plan_id: Optional[UUID] = Query(None),
    finding_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    try:
        container = get_approval_container()
        with container.session() as session:
            svc = container.build(session)
            filters = ApprovalSearchFilter(
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
                message="Approvals search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.post("/{approval_id}/cancel")
def cancel_approval(
    approval_id: UUID,
    body: CancelApprovalBody,
    tenant_id: UUID = Query(...),
):
    try:
        container = get_approval_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.cancel(
                    approval_id,
                    tenant_id,
                    reason=body.reason,
                    actor=body.actor,
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Approval cancelled",
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


@router.post("/{approval_id}/comments")
def add_comment(
    approval_id: UUID,
    body: CommentBody,
    tenant_id: UUID = Query(...),
):
    try:
        container = get_approval_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.add_comment(
                    approval_id,
                    tenant_id,
                    author=body.author,
                    body=body.body,
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Comment added",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/{approval_id}/authorization")
def get_authorization(approval_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_approval_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.authorization(approval_id, tenant_id)
            )
            return success_response(
                data=dump(result) if result else None,
                latency_ms=latency,
                message="Execution authorization",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/{approval_id}")
def get_approval(approval_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_approval_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.get(approval_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Approval retrieved",
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
