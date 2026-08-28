"""AIExecutionService — Context → Prompt → Provider with retry/timeout/fallback."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional, Tuple

from context.context_manager import ContextManager
from context.models import ContextRequest
from decision_engine import DecisionEngine
from decision_engine.models import DecisionResult, DecisionType
from prompt.prompt_builder import PromptBuilder
from providers.base_provider import BaseProvider
from providers.exceptions import ProviderError

from ai_harness.domain.enums import AuditAction
from ai_harness.domain.models import AIProviderResult, AIRequest
from ai_harness.exceptions import AIProviderExhaustedError, AITimeoutError
from ai_harness.services.provider_routing import AIProviderRoutingService

logger = logging.getLogger(__name__)


class AIExecutionService:
    """
    Execute one AI interaction through Architecture V2 primitives.

    Responsibilities: context assembly, prompt generation, provider invoke,
    timeout, retries, and fallback. No cybersecurity business logic.
    """

    def __init__(
        self,
        *,
        context_manager: Optional[ContextManager] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        routing: Optional[AIProviderRoutingService] = None,
        routing_decision: Optional[DecisionResult] = None,
        decision_engine: Optional[DecisionEngine] = None,
        audit_callback=None,
    ) -> None:
        self._context_manager = context_manager or ContextManager()
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._routing = routing or AIProviderRoutingService()
        self._decision_engine = decision_engine or DecisionEngine()
        self._routing_decision = routing_decision
        self._audit = audit_callback

    async def execute_with_resilience(
        self,
        request: AIRequest,
    ) -> Tuple[str, List[AIProviderResult], str]:
        """
        Returns (final_text, provider_attempts, selected_provider).

        Raises AIProviderExhaustedError when all providers fail.
        """

        chain = self._routing.resolve_chain(
            provider_name=request.provider_name,
            fallback_providers=request.fallback_providers,
        )
        await self._emit(
            AuditAction.PROVIDER_SELECTED,
            request,
            f"Provider chain={chain}",
            details={"chain": chain},
        )

        decision = self._routing_decision or self._decision_engine.route(
            request.message
        )
        context_request = ContextRequest(
            message=request.message,
            session_id=request.session_id,
        )
        ai_context = await self._context_manager.build(
            context_request,
            decision,
        )
        if request.system_prompt:
            ai_context.system_prompt = request.system_prompt
        elif not ai_context.system_prompt:
            ai_context.system_prompt = (
                "You are a helpful assistant inside the Xolaris AI Harness. "
                "Follow the user instructions precisely."
            )
        await self._emit(
            AuditAction.CONTEXT_BUILT,
            request,
            "Context assembled via ContextManager",
        )

        prompt = self._prompt_builder.build(ai_context)
        await self._emit(
            AuditAction.PROMPT_BUILT,
            request,
            "Prompt built via PromptBuilder",
            details={"message_count": len(prompt.messages)},
        )

        attempts: List[AIProviderResult] = []
        last_error: Optional[str] = None

        for idx, provider_name in enumerate(chain):
            if idx > 0:
                await self._emit(
                    AuditAction.PROVIDER_FALLBACK,
                    request,
                    f"Falling back to provider={provider_name}",
                    provider=provider_name,
                )
            provider = self._routing.get_provider(provider_name)
            for retry in range(request.max_retries + 1):
                attempt_no = retry + 1
                if retry > 0:
                    await self._emit(
                        AuditAction.RETRY_ATTEMPTED,
                        request,
                        f"Retry {retry} on provider={provider_name}",
                        provider=provider_name,
                        details={"attempt": attempt_no},
                    )
                    await asyncio.sleep(min(2.0, 0.25 * (2 ** (retry - 1))))

                result = await self._invoke_once(
                    provider,
                    prompt,
                    attempt=attempt_no,
                    timeout_seconds=request.timeout_seconds,
                )
                attempts.append(result)
                await self._emit(
                    AuditAction.PROVIDER_INVOKED,
                    request,
                    f"Provider invoked success={result.success}",
                    provider=provider_name,
                    details={
                        "attempt": attempt_no,
                        "latency_ms": result.latency_ms,
                        "success": result.success,
                    },
                )
                if result.success:
                    return result.text, attempts, provider_name
                last_error = result.error

        raise AIProviderExhaustedError(
            last_error or "All providers failed",
            details={
                "attempts": [a.model_dump(mode="json") for a in attempts],
                "chain": chain,
            },
        )

    async def _invoke_once(
        self,
        provider: BaseProvider,
        prompt,
        *,
        attempt: int,
        timeout_seconds: float,
    ) -> AIProviderResult:
        started = time.perf_counter()
        try:
            raw = await asyncio.wait_for(
                provider.generate(prompt),
                timeout=timeout_seconds,
            )
            latency = (time.perf_counter() - started) * 1000.0
            return AIProviderResult(
                provider=raw.provider or provider.provider_name,
                model=raw.model or "unknown",
                text=raw.text or "",
                finish_reason=raw.finish_reason,
                usage=dict(raw.usage or {}),
                metadata=dict(raw.metadata or {}),
                latency_ms=round(latency, 3),
                attempt=attempt,
                success=True,
            )
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - started) * 1000.0
            return AIProviderResult(
                provider=provider.provider_name,
                model="unknown",
                text="",
                latency_ms=round(latency, 3),
                attempt=attempt,
                success=False,
                error=f"Timed out after {timeout_seconds}s",
            )
        except ProviderError as exc:
            latency = (time.perf_counter() - started) * 1000.0
            return AIProviderResult(
                provider=provider.provider_name,
                model="unknown",
                text="",
                latency_ms=round(latency, 3),
                attempt=attempt,
                success=False,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            latency = (time.perf_counter() - started) * 1000.0
            logger.exception("Unexpected provider failure")
            return AIProviderResult(
                provider=provider.provider_name,
                model="unknown",
                text="",
                latency_ms=round(latency, 3),
                attempt=attempt,
                success=False,
                error=str(exc),
            )

    async def _emit(
        self,
        action: AuditAction,
        request: AIRequest,
        message: str,
        *,
        provider: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        if self._audit is None:
            return
        self._audit(
            action=action,
            message=message,
            tenant_id=request.tenant_id,
            request_id=request.id,
            actor=request.actor,
            provider=provider,
            details=details or {},
        )
