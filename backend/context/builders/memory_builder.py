"""
Long-term memory context builder (scaffold).

Phase 0 returns an empty ``MemoryContext``. Future versions will query a
dedicated memory store / summarizer without changing the ``build`` contract.
"""

from __future__ import annotations

import logging

from context.builders.base_builder import BaseContextBuilder
from context.models import ContextRequest, MemoryContext
from decision_engine.models import DecisionResult

logger = logging.getLogger(__name__)


class MemoryBuilder(BaseContextBuilder):
    """
    Builds long-term memory context for ``AIContext.memory``.

    Distinct from short-term conversation history (see ConversationBuilder).
    Does not call or modify ``MemoryService`` in this phase.
    """

    @property
    def field_name(self) -> str:
        """Populate ``AIContext.memory``."""

        return "memory"

    async def build(
        self,
        request: ContextRequest,
        decision: DecisionResult,
    ) -> MemoryContext:
        """
        Assemble long-term memory for the request.

        Args:
            request: Normalized context request.
            decision: Routing decision (e.g. MEMORY path in future).

        Returns:
            Empty ``MemoryContext`` scaffold.
        """

        logger.info(
            "MemoryBuilder: returning empty memory (scaffold) decision=%s session_id=%s",
            decision.decision_type.value,
            request.session_id,
        )
        return MemoryContext(
            metadata={
                "builder": self.__class__.__name__,
                "strategy": "empty_scaffold",
            }
        )
