"""Scan / Ingest HTTP API."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter
from pydantic import Field

from api.deps import dump, get_scan_ingest_container, map_engine_error, timed_call_async
from models.common import ActorReference, FortiBaseModel
from scan_ingest.domain.enums import ScanMode
from scan_ingest.domain.models import ScanRequest
from utils.response import error_response, success_response

router = APIRouter(prefix="/scans", tags=["Scan / Ingest"])


class ScanAPIRequest(FortiBaseModel):
    """HTTP body for POST /scans."""

    tenant_id: UUID = Field(...)
    target: str = Field(..., min_length=1, max_length=2048)
    tool_name: str = Field(default="nuclei", min_length=1, max_length=64)
    mode: ScanMode = Field(default=ScanMode.SIMULATE)
    asset_id: Optional[UUID] = None
    asset_name: Optional[str] = None
    run_pipeline: bool = Field(default=True)
    invoke_ai_decision: bool = Field(default=False)
    roles: List[str] = Field(default_factory=lambda: ["secops"])
    actor_display_name: str = Field(default="api-operator", max_length=256)
    tags: List[str] = Field(default_factory=list)


@router.post("")
async def run_scan(body: ScanAPIRequest):
    """
    Run scan → normalize → evidence ingest, optionally Trust→Risk→Decision→Plan.

    Default ``mode=simulate`` needs no scanner binary.
    """

    try:
        container = get_scan_ingest_container()
        request = ScanRequest(
            tenant_id=body.tenant_id,
            target=body.target,
            tool_name=body.tool_name,
            mode=body.mode,
            asset_id=body.asset_id,
            asset_name=body.asset_name,
            actor=ActorReference(
                actor_id=uuid4(),
                display_name=body.actor_display_name,
            ),
            roles=body.roles,
            run_pipeline=body.run_pipeline,
            invoke_ai_decision=body.invoke_ai_decision,
            tags=body.tags,
        )
        with container.session_scope(enable_pipeline=body.run_pipeline) as svc:

            async def _run():
                return await svc.engine.scan_async(request)

            result, latency = await timed_call_async(_run)
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Scan completed",
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
