"""
Decision Engine — Architecture V2 entry point for AI request routing.

Owns *routing decisions only*. First hop in ``LLMService`` when the V2 stack
is enabled, before ContextManager / PromptBuilder / ProviderFactory.
"""

from __future__ import annotations

import logging
from typing import Optional

from decision_engine.intent_router import IntentRouter
from decision_engine.models import DecisionResult

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Facade that routes inbound AI messages to a decision outcome.

    SOLID notes:
        - Single Responsibility: orchestrate routing; no side effects.
        - Open/Closed: new routers or policies can be injected.
        - Liskov: any object exposing ``detect_intent(str) -> DecisionResult``
          can be supplied as ``intent_router``.
        - Dependency Inversion: depends on the IntentRouter abstraction
          via constructor injection (defaults to a concrete instance).
    """

    def __init__(self, intent_router: Optional[IntentRouter] = None) -> None:
        self._intent_router: IntentRouter = intent_router or IntentRouter()
        logger.debug(
            "DecisionEngine initialized with intent_router=%s",
            type(self._intent_router).__name__,
        )

    @property
    def intent_router(self) -> IntentRouter:
        """Return the configured intent router (useful for tests)."""

        return self._intent_router

    def route(self, message: str) -> DecisionResult:
        """
        Route a user message to a ``DecisionResult``.

        Args:
            message: Raw user text to classify / route.

        Returns:
            DecisionResult: Outcome from ``IntentRouter.detect_intent``.
        """

        logger.info("DecisionEngine.route invoked")
        result = self._intent_router.detect_intent(message)
        logger.info(
            "DecisionEngine.route completed: type=%s confidence=%.2f",
            result.decision_type.value,
            result.confidence,
        )
        return result
