"""
RAG document context builder (scaffold).

Phase 0 returns an empty document list. Future versions will call a
retriever / vector store using ``request.message`` and ``decision``.
"""

from __future__ import annotations

import logging
from typing import List

from context.builders.base_builder import BaseContextBuilder
from context.models import ContextRequest, DocumentChunk
from decision_engine.models import DecisionResult

logger = logging.getLogger(__name__)


class RAGBuilder(BaseContextBuilder):
    """
    Builds retrieval-augmented document context for ``AIContext.documents``.

    Single Responsibility: document retrieval assembly only.
    """

    @property
    def field_name(self) -> str:
        """Populate ``AIContext.documents``."""

        return "documents"

    async def build(
        self,
        request: ContextRequest,
        decision: DecisionResult,
    ) -> List[DocumentChunk]:
        """
        Retrieve grounding documents for the request.

        Args:
            request: Normalized context request (query text in ``message``).
            decision: Routing decision (RAG path may alter top-k later).

        Returns:
            Empty list in phase 0.
        """

        logger.info(
            "RAGBuilder: returning empty documents (scaffold) decision=%s "
            "message_length=%s",
            decision.decision_type.value,
            len(request.message or ""),
        )
        return []
