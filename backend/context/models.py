"""
Domain models for the Context Manager layer.

``AIContext`` is the assembled payload that Architecture V2 will later feed
into PromptBuilder. Models here stay free of FastAPI and provider concerns
so builders remain independently unit-testable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Union

from pydantic import BaseModel, Field

from decision_engine.models import DecisionResult

RequestLike = Union["ContextRequest", Mapping[str, Any], Any]


class ContextRequest(BaseModel):
    """
    Normalized inbound request shape used by ContextManager builders.

    Mirrors the fields needed from the chat API without importing API
    routers, so this package can evolve independently of FastAPI contracts.

    Attributes:
        message: Current user utterance.
        session_id: Optional conversation / session identifier.
    """

    message: str = Field(..., description="Current user message text.")
    session_id: Optional[str] = Field(
        default=None,
        description="Session key used to load conversation history.",
    )

    @classmethod
    def coerce(cls, request: RequestLike) -> ContextRequest:
        """
        Coerce supported request shapes into ``ContextRequest``.

        Kept on the model (not on ContextManager) so the orchestrator stays
        free of input-normalization logic.

        Supports:
            - ContextRequest instances
            - Mapping objects with ``message`` / ``session_id``
            - Pydantic models with ``model_dump``
            - Duck-typed objects with ``message`` / ``session_id`` attributes
        """

        if isinstance(request, ContextRequest):
            return request

        if isinstance(request, Mapping):
            return cls(
                message=str(request.get("message", "")),
                session_id=request.get("session_id"),
            )

        if hasattr(request, "model_dump") and callable(request.model_dump):
            payload = request.model_dump()
            return cls(
                message=str(payload.get("message", "")),
                session_id=payload.get("session_id"),
            )

        message = getattr(request, "message", "")
        session_id = getattr(request, "session_id", None)
        return cls(message=str(message), session_id=session_id)


class ConversationMessage(BaseModel):
    """A single turn in short-term conversational history."""

    role: str = Field(..., description="Message role, e.g. user or assistant.")
    content: str = Field(..., description="Message body.")


class MemoryContext(BaseModel):
    """
    Long-term / structured memory slice for the current request.

    Phase 0 scaffold: builders return an empty instance. Future versions
    will populate summaries, facts, and preferences.
    """

    facts: List[str] = Field(default_factory=list)
    summaries: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """A retrieved document fragment used for RAG grounding."""

    id: str = Field(default="", description="Document or chunk identifier.")
    content: str = Field(default="", description="Chunk text.")
    score: float = Field(default=0.0, description="Retrieval relevance score.")
    source: str = Field(default="", description="Origin path, URL, or corpus id.")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProfileContext(BaseModel):
    """User or tenant profile attributes relevant to prompting."""

    user_id: Optional[str] = None
    display_name: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result of a single tool invocation included in context."""

    tool_name: str = Field(default="", description="Registered tool identifier.")
    status: str = Field(default="empty", description="success | error | empty.")
    output: Any = Field(default=None, description="Structured or textual tool output.")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIContext(BaseModel):
    """
    Complete context assembly for an LLM call in Architecture V2.

    Attributes:
        version: Schema version for forward-compatible consumers.
        request: Normalized inbound request.
        conversation: Short-term chat turns for the session.
        memory: Long-term memory slice (facts, summaries, preferences).
        documents: RAG document chunks.
        profile: User / tenant profile context.
        tool_results: Outputs from prior or planned tool calls.
        system_prompt: Optional system prompt override / fragment.
        metadata: Cross-cutting diagnostics and builder signals.
        decision: Routing decision from DecisionEngine.
    """

    version: str = Field(
        default="1.0",
        description="AIContext schema version.",
    )
    request: ContextRequest
    conversation: List[ConversationMessage] = Field(default_factory=list)
    memory: MemoryContext = Field(default_factory=MemoryContext)
    documents: List[DocumentChunk] = Field(default_factory=list)
    profile: ProfileContext = Field(default_factory=ProfileContext)
    tool_results: List[ToolResult] = Field(default_factory=list)
    system_prompt: Optional[str] = Field(
        default=None,
        description="Optional system prompt fragment; PromptBuilder may own the canonical prompt.",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    decision: DecisionResult
