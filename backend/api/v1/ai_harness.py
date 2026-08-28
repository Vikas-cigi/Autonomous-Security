"""AI Harness HTTP API (orchestration only — not chat LLMService)."""

from __future__ import annotations

from fastapi import APIRouter

from ai_harness.domain.models import AIRequest
from api.deps import (
    dump,
    get_ai_harness_container,
    map_engine_error,
    timed_call_async,
)
from utils.response import error_response, success_response

router = APIRouter(prefix="/ai-harness", tags=["AI Harness"])


@router.post("/run")
async def run_harness(body: AIRequest):
    try:
        container = get_ai_harness_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = await timed_call_async(lambda: svc.harness.run(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="AI harness run completed",
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
