"""
Domain models for the Decision Engine.

These types describe *what* path an AI request should take. They are
intentionally free of FastAPI, LLM, and provider concerns so the decision
layer stays independently testable and reusable across Architecture V2.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    """
    Classification of how an inbound AI request should be handled.

    Attributes:
        CHAT: Direct conversational completion (default path today).
        TOOL: Invoke one or more tools / function calls.
        RAG: Retrieve grounding context before generation.
        MEMORY: Memory-centric operations (recall, store, summarize).
        AGENT: Multi-step agentic planning / execution.
        UNKNOWN: Intent could not be classified with acceptable confidence.
    """

    CHAT = "CHAT"
    TOOL = "TOOL"
    RAG = "RAG"
    MEMORY = "MEMORY"
    AGENT = "AGENT"
    UNKNOWN = "UNKNOWN"


class DecisionResult(BaseModel):
    """
    Outcome of routing an inbound user message through the Decision Engine.

    Attributes:
        decision_type: Selected handling path for the request.
        confidence: Model or rule confidence in ``[0.0, 1.0]``.
        reason: Human-readable explanation of why this decision was chosen.
        metadata: Optional structured extras (signals, scores, debug flags).
    """

    decision_type: DecisionType = Field(
        ...,
        description="Selected Architecture V2 handling path.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score in the closed interval [0.0, 1.0].",
    )
    reason: str = Field(
        ...,
        description="Short explanation of the routing decision.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible bag for routing signals and diagnostics.",
    )

    def is_chat(self) -> bool:
        """Return True when the decision resolves to the CHAT path."""

        return self.decision_type is DecisionType.CHAT

    def with_metadata(self, **extra: Any) -> DecisionResult:
        """
        Return a copy of this result with additional metadata merged in.

        Existing keys are overwritten by ``extra``. The original instance
        is not mutated (immutability-friendly for tests and pipelines).
        """

        merged: Dict[str, Any] = {**self.metadata, **extra}
        return self.model_copy(update={"metadata": merged})
