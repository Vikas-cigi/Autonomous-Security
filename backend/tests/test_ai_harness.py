"""Unit tests for Enterprise AI Harness (SQLite + fake provider)."""

from __future__ import annotations

import asyncio
import unittest
from uuid import uuid4

from prompt.models import Prompt
from providers.base_provider import BaseProvider
from providers.models import AIResponse as ProviderAIResponse
from providers.provider_factory import ProviderFactory

from ai_harness import (
    AIExecutionStatus,
    AIHarnessContainer,
    AIRequest,
    ReflectionMode,
)
from ai_harness.exceptions import AIExecutionNotFoundError, AIValidationError
from ai_harness.query.filters import AIExecutionSearchFilter
from ai_harness.query.pagination import PageRequest
from ai_harness.services.validation import AIValidationService


class FakeProvider(BaseProvider):
    def __init__(
        self,
        name: str = "fake",
        text: str = '{"ok": true, "value": 1}',
        *,
        fail_times: int = 0,
    ) -> None:
        self._name = name
        self._text = text
        self._fail_times = fail_times
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return self._name

    async def generate(self, prompt: Prompt) -> ProviderAIResponse:
        self.calls += 1
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("transient failure")
        return ProviderAIResponse(
            text=self._text,
            provider=self._name,
            model="fake-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            finish_reason="stop",
        )


def _run(coro):
    return asyncio.run(coro)


def _request(**overrides) -> AIRequest:
    data = {
        "tenant_id": uuid4(),
        "message": "Return JSON with ok and value.",
        "provider_name": "fake",
        "expect_json": True,
        "required_json_keys": ["ok", "value"],
        "max_retries": 1,
        "timeout_seconds": 5.0,
        "reflection_mode": ReflectionMode.DISABLED,
    }
    data.update(overrides)
    return AIRequest(**data)


class AIValidationServiceTests(unittest.TestCase):
    def test_required_keys_and_schema(self) -> None:
        svc = AIValidationService()
        req = _request(
            json_schema={
                "type": "object",
                "required": ["ok", "value"],
                "properties": {
                    "ok": {"type": "boolean"},
                    "value": {"type": "integer"},
                },
            }
        )
        result = svc.validate(req, '{"ok": true, "value": 2}')
        self.assertTrue(result.valid)
        self.assertEqual(result.parsed_payload["value"], 2)

    def test_invalid_json(self) -> None:
        svc = AIValidationService()
        result = svc.validate(_request(), "not-json")
        self.assertFalse(result.valid)


class AIHarnessOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = FakeProvider()
        factory = ProviderFactory(
            providers={"fake": self.fake, "llama": self.fake},
            default_provider="fake",
        )
        self.container = AIHarnessContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
            provider_factory=factory,
        )

    def test_successful_run(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = _run(svc.harness.run(req))
            self.assertTrue(result.success)
            self.assertEqual(result.status, AIExecutionStatus.SUCCEEDED)
            self.assertIsNotNone(result.response)
            assert result.response is not None
            self.assertEqual(result.response.structured_payload["ok"], True)
            self.assertGreaterEqual(result.response.confidence.score, 0.5)
            self.assertEqual(result.response.usage.total_tokens, 15)
            self.assertEqual(self.fake.calls, 1)
            loaded = svc.harness.get_execution(
                result.execution.id, req.tenant_id
            )
            self.assertEqual(loaded.id, result.execution.id)
            audits = svc.audit_repository.list_for_execution(
                result.execution.id, req.tenant_id
            )
            self.assertGreaterEqual(len(audits), 1)

    def test_retry_then_success(self) -> None:
        flaky = FakeProvider(fail_times=1)
        factory = ProviderFactory(
            providers={"fake": flaky},
            default_provider="fake",
        )
        container = AIHarnessContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
            provider_factory=factory,
        )
        req = _request(max_retries=2)
        with container.session() as session:
            svc = container.build(session)
            result = _run(svc.harness.run(req))
            self.assertTrue(result.success)
            self.assertEqual(flaky.calls, 2)
            self.assertGreaterEqual(result.execution.attempt_count, 2)

    def test_validation_failed_status(self) -> None:
        bad = FakeProvider(text="not json at all")
        factory = ProviderFactory(providers={"fake": bad}, default_provider="fake")
        container = AIHarnessContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
            provider_factory=factory,
        )
        req = _request()
        with container.session() as session:
            svc = container.build(session)
            result = _run(svc.harness.run(req))
            self.assertFalse(result.success)
            self.assertEqual(result.status, AIExecutionStatus.VALIDATION_FAILED)

    def test_raise_on_validation_error(self) -> None:
        bad = FakeProvider(text="nope")
        factory = ProviderFactory(providers={"fake": bad}, default_provider="fake")
        container = AIHarnessContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
            provider_factory=factory,
        )
        with container.session() as session:
            svc = container.build(session)
            with self.assertRaises(AIValidationError):
                _run(
                    svc.harness.run(
                        _request(),
                        raise_on_validation_error=True,
                    )
                )

    def test_tenant_isolation(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = _run(svc.harness.run(req))
            with self.assertRaises(AIExecutionNotFoundError):
                svc.harness.get_execution(result.execution.id, uuid4())

    def test_search(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = _run(svc.harness.run(req))
            page = svc.harness.search(
                AIExecutionSearchFilter(
                    tenant_id=req.tenant_id,
                    statuses=[AIExecutionStatus.SUCCEEDED],
                ),
                PageRequest(),
            )
            self.assertGreaterEqual(page.total_items, 1)
            self.assertTrue(any(i.id == result.execution.id for i in page.items))


if __name__ == "__main__":
    unittest.main()
