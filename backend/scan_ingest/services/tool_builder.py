"""ToolBuilder that executes ScanOrchestrator for TOOL decisions."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, List, Optional
from uuid import UUID, uuid4

from context.builders.base_builder import BaseContextBuilder
from context.models import ContextRequest, ToolResult
from decision_engine.models import DecisionResult, DecisionType
from models.common import ActorReference
from scan_ingest.domain.enums import ScanMode
from scan_ingest.domain.models import ScanRequest
from scan_ingest.services.target_parser import detect_tool_name, extract_target

logger = logging.getLogger(__name__)

ScanRunner = Callable[[ScanRequest], Awaitable[Any]]


class ScanToolBuilder(BaseContextBuilder):
    """
    When decision is TOOL (scan), run the scan orchestrator and attach
    ``ToolResult`` entries for PromptBuilder / ToolTemplate.
    """

    def __init__(
        self,
        *,
        scan_runner: ScanRunner,
        default_tenant_id: UUID,
        default_mode: ScanMode = ScanMode.SIMULATE,
        run_pipeline: bool = True,
    ) -> None:
        self._scan_runner = scan_runner
        self._tenant_id = default_tenant_id
        self._mode = default_mode
        self._run_pipeline = run_pipeline

    @property
    def field_name(self) -> str:
        return "tool_results"

    async def build(
        self,
        request: ContextRequest,
        decision: DecisionResult,
    ) -> List[ToolResult]:
        if decision.decision_type is not DecisionType.TOOL:
            return []

        meta = decision.metadata or {}
        tool_name = meta.get("tool_name") or detect_tool_name(request.message)
        try:
            target = meta.get("target") or extract_target(request.message)
        except Exception as exc:  # noqa: BLE001
            return [
                ToolResult(
                    tool_name=tool_name,
                    status="error",
                    output={"error": str(exc)},
                    metadata={"phase": "parse"},
                )
            ]

        actor = ActorReference(
            actor_id=uuid4(),
            display_name="chat-operator",
            email="chat@xolaris.local",
        )
        scan_req = ScanRequest(
            tenant_id=self._tenant_id,
            target=target,
            tool_name=tool_name,
            mode=self._mode,
            actor=actor,
            run_pipeline=self._run_pipeline,
            invoke_ai_decision=False,
            scan_id=f"chat-{request.session_id or uuid4()}",
            tags=["chat", "tool"],
        )

        try:
            result = await self._scan_runner(scan_req)
            summary = (
                result.to_chat_summary()
                if hasattr(result, "to_chat_summary")
                else result
            )
            status = "success"
            if hasattr(result, "status"):
                status_val = getattr(result.status, "value", str(result.status))
                if status_val in {"failed", "policy_denied"}:
                    status = "error"
                elif status_val == "partial":
                    status = "success"
            return [
                ToolResult(
                    tool_name=tool_name,
                    status=status,
                    output=summary,
                    metadata={
                        "target": target,
                        "mode": self._mode.value,
                        "source": "scan_tool_builder",
                    },
                )
            ]
        except Exception as exc:  # noqa: BLE001
            logger.exception("ScanToolBuilder failed target=%s", target)
            return [
                ToolResult(
                    tool_name=tool_name,
                    status="error",
                    output={"error": str(exc), "target": target},
                    metadata={"source": "scan_tool_builder"},
                )
            ]
