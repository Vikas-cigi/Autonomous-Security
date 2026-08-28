from typing import Any, Optional

from pydantic import BaseModel


class Metadata(BaseModel):
    request_id: str
    model: str
    latency_ms: float
    timestamp: str


class ErrorResponse(BaseModel):
    code: str
    details: str


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Any = None
    metadata: Metadata
    error: Optional[ErrorResponse] = None
