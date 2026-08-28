import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.deps import get_llm_service
from models.request_models import ChatRequest
from utils.response import success_response, error_response

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        llm = get_llm_service()
        session_id = request.session_id or str(uuid.uuid4())
        result = await llm.chat(session_id=session_id, message=request.message)
        data = {
            "session_id": session_id,
            "response": result["answer"],
            "usage": result["usage"],
        }
        if "decision" in result:
            data["decision"] = result["decision"]
        if "provider" in result:
            data["provider"] = result["provider"]
            data["model"] = result.get("model")
        return success_response(
            data=data,
            latency_ms=result["latency"],
            message="LLM Response Generated",
        )
    except Exception as e:
        return error_response(
            code="LLM_ERROR",
            details=str(e),
            message="Request Failed",
        )


@router.post("/chat/stream")
async def stream_chat(request: ChatRequest):
    llm = get_llm_service()
    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator():
        async for chunk in llm.stream_chat(
            session_id=session_id,
            message=request.message,
        ):
            yield chunk + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
