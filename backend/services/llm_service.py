"""
LLMService — chat orchestration for Xolaris.

Architecture V2 path (default when ``LLM_ENABLE_V2_STACK`` is True)::

    DecisionEngine → ContextManager → PromptBuilder → ProviderFactory.generate

Legacy V1 path (flag False)::

    MemoryService → PromptService → LlamaProvider.chat / stream_chat
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator, Dict, Optional

from context.builders.conversation_builder import ConversationBuilder
from context.builders.memory_builder import MemoryBuilder
from context.builders.profile_builder import ProfileBuilder
from context.builders.rag_builder import RAGBuilder
from context.builders.tool_builder import ToolBuilder
from context.context_manager import ContextManager
from context.models import ContextRequest
from core.config import settings
from decision_engine import DecisionEngine
from prompt.prompt_builder import PromptBuilder
from providers.llama_provider import LlamaProvider
from providers.provider_factory import ProviderFactory
from services.memory_service import MemoryService
from services.prompt_service import PromptService

logger = logging.getLogger(__name__)


class LLMService:
    """
    Chat facade used by ``/chat`` and ``/chat/stream``.

    When V2 is enabled, routes through Decision Engine and the Architecture V2
    context → prompt → provider stack. Conversation memory is shared with
    ``ConversationBuilder`` so history stays consistent across turns.
    """

    def __init__(
        self,
        *,
        enable_v2_stack: Optional[bool] = None,
        decision_engine: Optional[DecisionEngine] = None,
        context_manager: Optional[ContextManager] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        provider_factory: Optional[ProviderFactory] = None,
        memory_service: Optional[MemoryService] = None,
        prompt_service: Optional[PromptService] = None,
        provider_name: Optional[str] = None,
    ) -> None:
        self.enable_v2_stack = (
            settings.LLM_ENABLE_V2_STACK
            if enable_v2_stack is None
            else enable_v2_stack
        )
        self.memory_service = memory_service or MemoryService()
        self.prompt_service = prompt_service or PromptService()
        self.provider_name = provider_name
        self._decision_engine = decision_engine or DecisionEngine()
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._provider_factory = provider_factory or ProviderFactory()

        if context_manager is not None:
            self._context_manager = context_manager
        else:
            # Share the same MemoryService instance used for persistence.
            self._context_manager = ContextManager(
                builders=[
                    ConversationBuilder(memory_service=self.memory_service),
                    MemoryBuilder(),
                    RAGBuilder(),
                    ProfileBuilder(),
                    ToolBuilder(),
                ]
            )

        # Keep a direct LlamaProvider for V1 fallback / streaming helpers.
        self.provider = LlamaProvider()
        logger.info(
            "LLMService initialized v2_stack=%s",
            self.enable_v2_stack,
        )

    async def chat(self, session_id: str, message: str) -> Dict[str, Any]:
        if self.enable_v2_stack:
            result = await self._chat_v2(session_id=session_id, message=message)
        else:
            result = await self._chat_v1(session_id=session_id, message=message)

        self.memory_service.add_user_message(session_id, message)
        self.memory_service.add_assistant_message(session_id, result["answer"])
        return result

    async def stream_chat(
        self, session_id: str, message: str
    ) -> AsyncIterator[str]:
        if self.enable_v2_stack:
            async for chunk in self._stream_v2(session_id=session_id, message=message):
                yield chunk
        else:
            async for chunk in self._stream_v1(session_id=session_id, message=message):
                yield chunk

    # ------------------------------------------------------------------
    # V2 stack
    # ------------------------------------------------------------------

    async def _chat_v2(self, session_id: str, message: str) -> Dict[str, Any]:
        decision = self._decision_engine.route(message)
        request = ContextRequest(message=message, session_id=session_id)
        ai_context = await self._context_manager.build(request, decision)
        if not ai_context.system_prompt:
            ai_context.system_prompt = (
                "You are RavenX, the Xolaris cybersecurity assistant."
            )
        ai_context.metadata = {
            **(ai_context.metadata or {}),
            "decision_type": decision.decision_type.value,
            "decision_confidence": decision.confidence,
            "source": "llm_service_v2",
        }
        prompt = self._prompt_builder.build(ai_context)
        provider = self._resolve_provider()

        started = time.perf_counter()
        response = await provider.generate(prompt)
        latency = round((time.perf_counter() - started) * 1000, 2)

        usage = dict(response.usage or {})
        meta_latency = (response.metadata or {}).get("latency_ms")
        if meta_latency is not None:
            try:
                latency = float(meta_latency)
            except (TypeError, ValueError):
                pass

        logger.info(
            "LLMService.v2 chat decision=%s provider=%s latency_ms=%.1f",
            decision.decision_type.value,
            response.provider,
            latency,
        )
        return {
            "answer": response.text or "",
            "usage": usage,
            "latency": latency,
            "decision": {
                "type": decision.decision_type.value,
                "confidence": decision.confidence,
                "reason": decision.reason,
            },
            "provider": response.provider,
            "model": response.model,
        }

    async def _stream_v2(
        self, session_id: str, message: str
    ) -> AsyncIterator[str]:
        decision = self._decision_engine.route(message)
        request = ContextRequest(message=message, session_id=session_id)
        ai_context = await self._context_manager.build(request, decision)
        if not ai_context.system_prompt:
            ai_context.system_prompt = (
                "You are RavenX, the Xolaris cybersecurity assistant."
            )
        prompt = self._prompt_builder.build(ai_context)
        messages = prompt.as_openai_messages()

        # Prefer native streaming on LlamaProvider; otherwise emit one chunk.
        # Memory persistence matches V1 stream_chat (caller / non-stream chat owns it).
        provider = self._resolve_provider()
        if hasattr(provider, "stream_chat"):
            async for chunk in provider.stream_chat(messages):  # type: ignore[attr-defined]
                yield chunk
        else:
            response = await provider.generate(prompt)
            yield response.text or ""

    # ------------------------------------------------------------------
    # V1 legacy
    # ------------------------------------------------------------------

    async def _chat_v1(self, session_id: str, message: str) -> Dict[str, Any]:
        history = self.memory_service.get_history(session_id)
        messages = self.prompt_service.build_messages(history, message)
        return await self.provider.chat(messages)

    async def _stream_v1(
        self, session_id: str, message: str
    ) -> AsyncIterator[str]:
        history = self.memory_service.get_history(session_id)
        messages = self.prompt_service.build_messages(history, message)
        async for chunk in self.provider.stream_chat(messages):
            yield chunk

    def _resolve_provider(self):
        if self.provider_name:
            return self._provider_factory.get_provider(self.provider_name)
        return self._provider_factory.get_default_provider()
