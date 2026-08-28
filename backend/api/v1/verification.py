"""Verification Engine HTTP API."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import Field

from models.common import FortiBaseModel

from api.deps import dump, get_verification_container, map_engine_error, timed_call
from utils.response import error_response, success_response
from verification_engine.domain.inputs import VerificationRequest
from verification_engine.query.filters import VerificationSearchFilter
from verification_engine.query.pagination import PageRequest

router = APIRouter(prefix="/verifications", tags=["Verification Engine"])


class CancelVerificationBody(FortiBaseModel):
    reason: str = Field(default="Cancelled by operator", max_length=2000)
    actor: Optional[str] = Field(default=None, max_length=256)


class ReplayVerificationBody(FortiBaseModel):
    request: VerificationRequest
    actor: Optional[str] = Field(default=None, max_length=256)


@router.post("")
def verify(body: VerificationRequest):
    try:
        container = get_verification_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.engine.verify(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Verification completed",
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
def search_verifications(
    tenant_id: UUID = Query(...),
    execution_id: Optional[UUID] = Query(None),
    finding_id: Optional[UUID] = Query(None),
    plan_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    try:
        container = get_verification_container()
        with container.session() as session:
            svc = container.build(session)
            filters = VerificationSearchFilter(
                tenant_id=tenant_id,
                execution_id=execution_id,
                finding_id=finding_id,
                plan_id=plan_id,
            )
            result, latency = timed_call(
                lambda: svc.engine.search(
                    filters, PageRequest(page=page, page_size=page_size)
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Verifications search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.post("/{verification_id}/replay")
def replay_verification(
    verification_id: UUID,
    body: ReplayVerificationBody,
    tenant_id: UUID = Query(...),
):
    try:
        container = get_verification_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.replay(
                    verification_id,
                    tenant_id,
                    body.request,
                    actor=body.actor,
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Verification replayed",
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


@router.post("/{verification_id}/cancel")
def cancel_verification(
    verification_id: UUID,
    body: CancelVerificationBody,
    tenant_id: UUID = Query(...),
):
    try:
        container = get_verification_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.cancel(
                    verification_id,
                    tenant_id,
                    reason=body.reason,
                    actor=body.actor,
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Verification cancelled",
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


@router.get("/{verification_id}/versions")
def list_verification_versions(verification_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_verification_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.list_versions(verification_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Verification versions",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/{verification_id}")
def get_verification(verification_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_verification_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.get(verification_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Verification retrieved",
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
