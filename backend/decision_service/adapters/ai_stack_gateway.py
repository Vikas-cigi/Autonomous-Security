"""Adapter wrapping Architecture V2 AI stack (consume only — no modifications)."""

from __future__ import annotations

import logging
import time
from typing import Optional

from context.context_manager import ContextManager
from context.models import ContextRequest
from decision_engine import DecisionEngine
from decision_engine.models import DecisionResult, DecisionType
from prompt.prompt_builder import PromptBuilder
from providers.base_provider import BaseProvider
from providers.provider_factory import ProviderFactory

from decision_service.domain.models import (
    AIRequestEnvelope,
    AIResponseEnvelope,
    DecisionContext,
)
from decision_service.exceptions import AIOrchestrationError
from decision_service.interfaces.ai_gateway import AIDecisionGateway

logger = logging.getLogger(__name__)


class AIStackGateway(AIDecisionGateway):
    """
    Invoke DecisionEngine → ContextManager → PromptBuilder → ProviderFactory.generate.

    This adapter contains no cybersecurity business logic — it only wires
    Architecture V2 scaffolds for AI-assisted decision text generation.
    """

    def __init__(
        self,
        *,
        context_manager: Optional[ContextManager] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        provider_factory: Optional[ProviderFactory] = None,
        decision_engine: Optional[DecisionEngine] = None,
        routing_decision: Optional[DecisionResult] = None,
    ) -> None:
        self._context_manager = context_manager or ContextManager()
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._provider_factory = provider_factory or ProviderFactory()
        self._decision_engine = decision_engine or DecisionEngine()
        self._routing_decision = routing_decision

    async def invoke(
        self,
        context: DecisionContext,
        *,
        session_id: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> tuple[AIRequestEnvelope, AIResponseEnvelope]:
        try:
            request = ContextRequest(
                message=context.operator_message,
                session_id=session_id,
            )
            decision = self._routing_decision or self._decision_engine.route(
                context.operator_message
            )
            # Prefer AGENT intent for decision-service prompts when router
            # returns generic CHAT — keep explicit override if injected.
            if self._routing_decision is None and decision.decision_type == DecisionType.CHAT:
                decision = DecisionResult(
                    decision_type=DecisionType.AGENT,
                    confidence=decision.confidence,
                    reason="Decision Service cybersecurity decision request",
                    metadata={"source": "decision_service", "routed_as": "CHAT"},
                )
            ai_context = await self._context_manager.build(
                request,
                decision,
            )
            # Inject decision intelligence into system prompt extension path
            # without modifying ContextManager — attach via metadata-aware prompt.
            if not ai_context.system_prompt:
                ai_context.system_prompt = (
                    "You are the Xolaris Decision Service assistant. "
                    "Return a JSON object with keys: decision_type "
                    "(remediate|ignore|escalate|investigate|monitor), "
                    "confidence (0-1), recommended_action, next_step, "
                    "business_justification, technical_justification, explanation."
                )

            prompt = self._prompt_builder.build(ai_context)
            provider = self._resolve_provider(provider_name)

            started = time.perf_counter()
            raw = await provider.generate(prompt)
            latency_ms = (time.perf_counter() - started) * 1000.0

            ai_request = AIRequestEnvelope(
                session_id=session_id,
                provider_name=provider.provider_name,
                system_prompt=prompt.system_prompt or "",
                user_message=context.operator_message,
                prompt_metadata=dict(prompt.metadata or {}),
                context_metadata={
                    "finding_id": str(context.finding_id),
                    "tenant_id": str(context.tenant_id),
                    "trust_score": context.trust_score,
                    "enterprise_risk_score": context.enterprise_risk_score,
                    "builder": "AIStackGateway",
                },
            )
            ai_response = AIResponseEnvelope(
                provider=raw.provider,
                model=raw.model,
                text=raw.text or "",
                finish_reason=raw.finish_reason,
                usage=dict(raw.usage or {}),
                metadata=dict(raw.metadata or {}),
                latency_ms=round(latency_ms, 3),
            )
            logger.info(
                "AIStackGateway.invoke complete provider=%s latency_ms=%.1f",
                ai_response.provider,
                latency_ms,
            )
            return ai_request, ai_response
        except AIOrchestrationError:
            raise
        except Exception as exc:  # noqa: BLE001 — boundary adapter
            raise AIOrchestrationError(
                f"AI stack orchestration failed: {exc}",
                details={"error": str(exc)},
            ) from exc

    def _resolve_provider(self, provider_name: Optional[str]) -> BaseProvider:
        if provider_name:
            return self._provider_factory.get_provider(provider_name)
        return self._provider_factory.get_default_provider()
