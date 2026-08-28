"""
Conversation history builder.

Uses ``MemoryService.get_history`` to load short-term turns for a session.
Does not write memory and does not modify ``MemoryService``.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Protocol

from context.builders.base_builder import BaseContextBuilder
from context.models import ContextRequest, ConversationMessage
from decision_engine.models import DecisionResult

logger = logging.getLogger(__name__)


class SupportsMemoryHistory(Protocol):
    """
    Narrow protocol for conversation history lookup.

    Matches ``MemoryService.get_history`` so production code can inject the
    real service while tests inject fakes — without subclassing requirements.
    """

    def get_history(self, session_id: str) -> List[dict]:
        """Return prior messages for ``session_id``."""


class ConversationBuilder(BaseContextBuilder):
    """
    Builds short-term conversational context for ``AIContext.conversation``.

    SOLID notes:
        - Single Responsibility: conversation turns only.
        - Open/Closed: swap MemoryService via constructor injection.
        - Liskov: honors ``BaseContextBuilder`` async contract.
        - Dependency Inversion: depends on ``SupportsMemoryHistory``.
    """

    def __init__(self, memory_service: Optional[SupportsMemoryHistory] = None) -> None:
        """
        Args:
            memory_service: Service exposing ``get_history(session_id)``.
                When omitted, a real ``MemoryService`` instance is created.
                Callers that share LLMService's memory should inject that
                instance at integration time (not done in this phase).
        """

        if memory_service is None:
            # Local import keeps optional wiring lazy and avoids circular imports.
            from services.memory_service import MemoryService

            memory_service = MemoryService()

        self._memory_service: SupportsMemoryHistory = memory_service
        logger.debug(
            "ConversationBuilder initialized with memory_service=%s",
            type(self._memory_service).__name__,
        )

    @property
    def field_name(self) -> str:
        """Populate ``AIContext.conversation``."""

        return "conversation"

    async def build(
        self,
        request: ContextRequest,
        decision: DecisionResult,
    ) -> List[ConversationMessage]:
        """
        Load conversation history for the request session.

        Args:
            request: Normalized context request (needs ``session_id``).
            decision: Routing decision (unused in phase 0; reserved for
                future decision-aware history windows).

        Returns:
            List of ``ConversationMessage``. Empty when ``session_id`` is
            missing or no history exists.
        """

        _ = decision  # reserved for future trimming / window strategies

        session_id = request.session_id
        if not session_id:
            logger.info(
                "ConversationBuilder: no session_id; returning empty conversation"
            )
            return []

        # Sync MemoryService today; await keeps the contract I/O-ready.
        raw_history = self._memory_service.get_history(session_id)
        messages: List[ConversationMessage] = []

        for item in raw_history or []:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", ""))
            if not role:
                logger.debug(
                    "ConversationBuilder: skipping history item without role: %s",
                    item,
                )
                continue
            messages.append(ConversationMessage(role=role, content=content))

        logger.info(
            "ConversationBuilder: session_id=%s turns=%s",
            session_id,
            len(messages),
        )
        return messages
