"""
User / tenant profile context builder (scaffold).

Phase 0 returns an empty ``ProfileContext``. Future versions will load
identity, roles, and preferences from a profile service.
"""

from __future__ import annotations

import logging

from context.builders.base_builder import BaseContextBuilder
from context.models import ContextRequest, ProfileContext
from decision_engine.models import DecisionResult

logger = logging.getLogger(__name__)


class ProfileBuilder(BaseContextBuilder):
    """
    Builds profile context for ``AIContext.profile``.

    Single Responsibility: profile attributes only.
    """

    @property
    def field_name(self) -> str:
        """Populate ``AIContext.profile``."""

        return "profile"

    async def build(
        self,
        request: ContextRequest,
        decision: DecisionResult,
    ) -> ProfileContext:
        """
        Load profile attributes for the request.

        Args:
            request: Normalized context request.
            decision: Routing decision (reserved for persona-aware routing).

        Returns:
            Empty ``ProfileContext`` scaffold.
        """

        logger.info(
            "ProfileBuilder: returning empty profile (scaffold) decision=%s",
            decision.decision_type.value,
        )
        return ProfileContext(
            metadata={
                "builder": self.__class__.__name__,
                "strategy": "empty_scaffold",
            }
        )
