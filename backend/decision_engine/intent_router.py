"""
Intent detection for the Decision Engine.

``IntentRouter`` is responsible solely for classifying a user message into a
``DecisionResult``. It does not invoke LLMs, tools, memory, or providers.

Current phase (Architecture V2 scaffold):
    Always classify as ``DecisionType.CHAT`` with confidence ``1.0``.
    Real NLP / LLM-based classification will replace this stub later without
    changing the public ``detect_intent`` contract.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from decision_engine.models import DecisionResult, DecisionType

logger = logging.getLogger(__name__)


class IntentRouter:
    """
    Maps a raw user message to a ``DecisionResult``.

    Designed for dependency injection: ``DecisionEngine`` accepts an
    ``IntentRouter`` (or compatible object) so unit tests can supply fakes
    without patching globals.

    SOLID notes:
        - Single Responsibility: intent classification only.
        - Open/Closed: subclass or inject alternate routers for new strategies.
        - Interface Segregation: one public method — ``detect_intent``.
        - Dependency Inversion: consumers depend on this narrow contract.
    """

    def __init__(self, default_metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the router.

        Args:
            default_metadata: Optional base metadata merged into every result.
                Useful for tagging environment, version, or experiment ids
                in tests and future rollouts.
        """

        self._default_metadata: Dict[str, Any] = dict(default_metadata or {})
        logger.debug(
            "IntentRouter initialized with default_metadata_keys=%s",
            sorted(self._default_metadata.keys()),
        )

    def detect_intent(self, message: str) -> DecisionResult:
        """
        Detect the handling intent for ``message``.

        Args:
            message: Raw user text from the client request.

        Returns:
            DecisionResult: Always ``CHAT`` with confidence ``1.0`` in this
            scaffold phase. Future versions may return TOOL, RAG, MEMORY,
            AGENT, or UNKNOWN based on classifiers.

        Notes:
            Empty or whitespace-only messages still return CHAT so callers
            remain stable; validation belongs to the API / LLM layer.
        """

        normalized_length = len(message.strip()) if message is not None else 0

        metadata: Dict[str, Any] = {
            **self._default_metadata,
            "router": self.__class__.__name__,
            "message_length": normalized_length,
            "strategy": "passthrough_chat",
        }

        result = DecisionResult(
            decision_type=DecisionType.CHAT,
            confidence=1.0,
            reason=(
                "Scaffold IntentRouter: all messages default to CHAT "
                "until classifiers are enabled."
            ),
            metadata=metadata,
        )

        logger.info(
            "Intent detected: type=%s confidence=%.2f message_length=%s",
            result.decision_type.value,
            result.confidence,
            normalized_length,
        )
        logger.debug("Intent reason=%s metadata=%s", result.reason, result.metadata)

        return result
