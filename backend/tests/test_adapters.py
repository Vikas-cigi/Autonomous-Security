"""Unit tests for the Xolaris Security Tool Adapter Framework."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from models.common import ActorReference
from models.enums import ActionClass, PolicyScope, PolicyVerdict
from policy_engine.models import PolicyDecision

from src.adapters.base.factory import AdapterFactory
from src.adapters.base.raw_result import RawResult, RawResultStatus
from src.adapters.base.registry import AdapterRegistry
from src.adapters.common.execution_context import AdapterExecutionContext
from src.adapters.nuclei.config import NucleiAdapterConfig
from src.adapters.nuclei.parser import NucleiParser
from src.adapters.trivy.config import TrivyAdapterConfig
from src.adapters.trivy.parser import TrivyParser
from src.adapters.checkov.config import CheckovAdapterConfig
from src.adapters.checkov.parser import CheckovParser
from src.adapters.prowler.config import ProwlerAdapterConfig
from src.adapters.prowler.parser import ProwlerParser


def _context(**kwargs) -> AdapterExecutionContext:
    base = dict(
        tenant_id=uuid4(),
        asset_id=uuid4(),
        user=ActorReference(actor_id=uuid4(), display_name="tester", email="t@xolaris.io"),
        roles=["secops"],
        scope=PolicyScope.TENANT,
        action_class=ActionClass.SIMULATE,
        targets=["https://example.com"],
        allowed_targets=["https://example.com"],
        tags=["unit-test"],
    )
    base.update(kwargs)
    return AdapterExecutionContext(**base)


def _allow_decision(tenant_id, resource_id) -> PolicyDecision:
    return PolicyDecision(
        verdict=PolicyVerdict.ALLOW,
        reason="test allow",
        action_class=ActionClass.SIMULATE,
        tenant_id=tenant_id,
        resource_id=resource_id,
        matched_rule_ids=[uuid4()],
        policy_version="test-1.0.0",
    )


class RegistryFactoryTests(unittest.TestCase):
    def test_builtin_adapters_registered(self) -> None:
        import src.adapters  # noqa: F401

        tools = AdapterRegistry.list()
        for name in ("nuclei", "prowler", "trivy", "checkov"):
            self.assertIn(name, tools)

    def test_factory_creates_nuclei(self) -> None:
        import src.adapters  # noqa: F401

        factory = AdapterFactory()
        adapter = factory.create("nuclei", NucleiAdapterConfig())
        self.assertEqual(adapter.tool_name, "nuclei")


class ParserTests(unittest.TestCase):
    def test_nuclei_jsonl(self) -> None:
        payload = '{"template-id":"t1","info":{"name":"n","severity":"high"}}\n'
        items = NucleiParser().parse(payload, "", 0)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["template-id"], "t1")

    def test_trivy_json(self) -> None:
        payload = json.dumps({"Results": [{"Target": "img", "Vulnerabilities": []}]})
        data = TrivyParser().parse(payload, "", 0)
        self.assertIn("Results", data)

    def test_checkov_json(self) -> None:
        payload = json.dumps({"results": {"failed_checks": [{"check_id": "CKV_1"}]}})
        data = CheckovParser().parse(payload, "", 0)
        self.assertEqual(data["results"]["failed_checks"][0]["check_id"], "CKV_1")

    def test_prowler_list(self) -> None:
        payload = json.dumps([{"CheckID": "s3_bucket", "Status": "FAIL"}])
        data = ProwlerParser().parse(payload, "", 0)
        self.assertEqual(data[0]["CheckID"], "s3_bucket")


class AdapterLifecycleTests(unittest.TestCase):
    def test_nuclei_run_returns_raw_result_only(self) -> None:
        import src.adapters  # noqa: F401

        ctx = _context()
        policy = MagicMock()
        policy.evaluate.return_value = _allow_decision(ctx.tenant_id, ctx.asset_id)

        adapter = AdapterFactory(policy_engine=policy).create(
            "nuclei",
            NucleiAdapterConfig(binary_path="nuclei", max_retries=0),
        )

        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps(
            [{"template-id": "cve-1", "info": {"name": "x", "severity": "low"}}]
        )
        fake.stderr = ""

        with patch("src.adapters.base.base_adapter.subprocess.run", return_value=fake):
            with patch.object(adapter, "version", return_value="nuclei-test"):
                result = adapter.run(ctx)

        self.assertIsInstance(result, RawResult)
        self.assertEqual(result.tool_name, "nuclei")
        self.assertEqual(result.status, RawResultStatus.SUCCEEDED)
        self.assertIsInstance(result.raw_output, list)
        self.assertTrue(policy.evaluate.called)
        # Guarantee adapters do not emit canonical findings.
        self.assertFalse(hasattr(result, "findings"))

    def test_policy_deny_short_circuits_execution(self) -> None:
        import src.adapters  # noqa: F401

        ctx = _context()
        policy = MagicMock()
        policy.evaluate.return_value = PolicyDecision(
            verdict=PolicyVerdict.DENY,
            reason="denied by test",
            action_class=ActionClass.SIMULATE,
            tenant_id=ctx.tenant_id,
            resource_id=ctx.asset_id,
            matched_rule_ids=[],
            policy_version="test-1.0.0",
        )
        adapter = AdapterFactory(policy_engine=policy).create(
            "trivy",
            TrivyAdapterConfig(binary_path="trivy", max_retries=0),
        )
        with patch.object(adapter, "version", return_value="trivy-test"):
            with patch("src.adapters.base.base_adapter.subprocess.run") as run_mock:
                result = adapter.run(ctx)
        self.assertEqual(result.status, RawResultStatus.POLICY_DENIED)
        run_mock.assert_not_called()

    def test_scope_violation_for_unauthorized_target(self) -> None:
        import src.adapters  # noqa: F401

        ctx = _context(
            targets=["https://evil.example"],
            allowed_targets=["https://example.com"],
        )
        policy = MagicMock()
        policy.evaluate.return_value = _allow_decision(ctx.tenant_id, ctx.asset_id)
        adapter = AdapterFactory(policy_engine=policy).create(
            "checkov",
            CheckovAdapterConfig(binary_path="checkov", max_retries=0),
        )
        result = adapter.run(ctx)
        self.assertEqual(result.status, RawResultStatus.SCOPE_DENIED)


if __name__ == "__main__":
    unittest.main()
