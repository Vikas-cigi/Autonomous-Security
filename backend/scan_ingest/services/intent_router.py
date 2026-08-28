"""Scan-aware IntentRouter — TOOL for scan messages, CHAT otherwise."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from decision_engine.intent_router import IntentRouter
from decision_engine.models import DecisionResult, DecisionType
from scan_ingest.services.target_parser import (
    detect_tool_name,
    extract_target,
    is_scan_intent,
)

logger = logging.getLogger(__name__)


class ScanAwareIntentRouter(IntentRouter):
    """
    Extends scaffold IntentRouter without replacing CHAT behavior for
    non-scan messages.

    When a message matches scan intent AND includes a parseable target,
    returns ``DecisionType.TOOL`` with tool/target metadata for ToolBuilder.
    """

    def detect_intent(self, message: str) -> DecisionResult:
        if is_scan_intent(message):
            try:
                target = extract_target(message)
                tool = detect_tool_name(message)
                metadata: Dict[str, Any] = {
                    **self._default_metadata,
                    "router": self.__class__.__name__,
                    "strategy": "scan_tool",
                    "tool_name": tool,
                    "target": target,
                    "message_length": len(message.strip()) if message else 0,
                }
                result = DecisionResult(
                    decision_type=DecisionType.TOOL,
                    confidence=0.95,
                    reason=f"Scan intent detected for tool={tool} target={target}",
                    metadata=metadata,
                )
                logger.info(
                    "ScanAwareIntentRouter TOOL tool=%s target=%s",
                    tool,
                    target,
                )
                return result
            except Exception as exc:  # noqa: BLE001 — fall through to CHAT
                logger.info(
                    "Scan intent without usable target; falling back to CHAT (%s)",
                    exc,
                )

        # Preserve scaffold CHAT behavior for everything else.
        return super().detect_intent(message)
