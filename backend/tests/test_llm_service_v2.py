"""Unit tests for LLMService Architecture V2 wiring."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from decision_engine.models import DecisionResult, DecisionType
from prompt.models import Prompt, PromptMessage
from providers.models import AIResponse
from services.llm_service import LLMService
from services.memory_service import MemoryService


class LLMServiceV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_routes_decision_context_prompt_provider(self) -> None:
        memory = MemoryService()
        decision_engine = MagicMock()
        decision_engine.route.return_value = DecisionResult(
            decision_type=DecisionType.CHAT,
            confidence=0.9,
            reason="test",
        )

        context_manager = MagicMock()
        context_manager.build = AsyncMock(
            return_value=MagicMock(
                system_prompt="",
                metadata={},
            )
        )

        prompt_builder = MagicMock()
        prompt_builder.build.return_value = Prompt(
            system_prompt="sys",
            messages=[
                PromptMessage(role="system", content="sys"),
                PromptMessage(role="user", content="hello"),
            ],
        )

        provider = MagicMock()
        provider.provider_name = "fake"
        provider.generate = AsyncMock(
            return_value=AIResponse(
                text="hi",
                provider="fake",
                model="test",
                usage={"total_tokens": 3},
                metadata={"latency_ms": 12.5},
            )
        )
        factory = MagicMock()
        factory.get_default_provider.return_value = provider

        svc = LLMService(
            enable_v2_stack=True,
            decision_engine=decision_engine,
            context_manager=context_manager,
            prompt_builder=prompt_builder,
            provider_factory=factory,
            memory_service=memory,
        )

        result = await svc.chat(session_id="s1", message="hello")

        decision_engine.route.assert_called_once_with("hello")
        context_manager.build.assert_awaited()
        prompt_builder.build.assert_called_once()
        provider.generate.assert_awaited()
        self.assertEqual(result["answer"], "hi")
        self.assertEqual(result["decision"]["type"], "CHAT")
        self.assertEqual(len(memory.get_history("s1")), 2)

    async def test_legacy_v1_path_skips_decision_engine(self) -> None:
        memory = MemoryService()
        decision_engine = MagicMock()
        provider = MagicMock()
        provider.chat = AsyncMock(
            return_value={"answer": "legacy", "usage": {}, "latency": 1.0}
        )

        svc = LLMService(
            enable_v2_stack=False,
            decision_engine=decision_engine,
            memory_service=memory,
        )
        svc.provider = provider

        result = await svc.chat(session_id="s2", message="ping")
        decision_engine.route.assert_not_called()
        self.assertEqual(result["answer"], "legacy")


if __name__ == "__main__":
    unittest.main()
