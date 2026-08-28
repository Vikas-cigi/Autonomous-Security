"""
Tool-result context builder (scaffold).

Phase 0 returns an empty tool-result list. Future versions will attach
outputs from tool / function-calling pipelines selected by DecisionEngine.
"""

from __future__ import annotations

import logging
from typing import List

from context.builders.base_builder import BaseContextBuilder
from context.models import ContextRequest, ToolResult
from decision_engine.models import DecisionResult

logger = logging.getLogger(__name__)


class ToolBuilder(BaseContextBuilder):
    """
    Builds tool-result context for ``AIContext.tool_results``.

    Single Responsibility: tool output assembly only.
    """

    @property
    def field_name(self) -> str:
        """Populate ``AIContext.tool_results``."""

        return "tool_results"

    async def build(
        self,
        request: ContextRequest,
        decision: DecisionResult,
    ) -> List[ToolResult]:
        """
        Assemble tool results relevant to the request.

        Args:
            request: Normalized context request.
            decision: Routing decision (TOOL / AGENT paths later).

        Returns:
            Empty list in phase 0.
        """

        logger.info(
            "ToolBuilder: returning empty tool_results (scaffold) decision=%s",
            decision.decision_type.value,
        )
        return []
