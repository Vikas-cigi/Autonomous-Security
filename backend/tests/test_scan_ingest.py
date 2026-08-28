"""Tests for Scan / Ingest orchestrator wiring."""

from __future__ import annotations

import unittest
from uuid import uuid4

from models.common import ActorReference
from scan_ingest import (
    ScanAwareIntentRouter,
    ScanIngestContainer,
    ScanMode,
    ScanRequest,
    ScanStatus,
)
from scan_ingest.services.target_parser import (
    extract_target,
    is_scan_intent,
    parse_scan_message,
)
from decision_engine.models import DecisionType


class TargetParserTests(unittest.TestCase):
    def test_scan_intent(self) -> None:
        self.assertTrue(is_scan_intent("Please scan https://api.example.com"))
        self.assertFalse(is_scan_intent("What is a CVE?"))

    def test_extract_target(self) -> None:
        self.assertEqual(
            extract_target("scan api.example.com for vulns"),
            "https://api.example.com",
        )
        self.assertEqual(
            extract_target("run nuclei on https://target.lab/app"),
            "https://target.lab/app",
        )

    def test_parse_scan_message(self) -> None:
        tool, target = parse_scan_message("nuclei scan https://x.test")
        self.assertEqual(tool, "nuclei")
        self.assertEqual(target, "https://x.test")


class IntentRouterTests(unittest.TestCase):
    def test_tool_for_scan(self) -> None:
        result = ScanAwareIntentRouter().detect_intent(
            "scan https://vulnerable.example"
        )
        self.assertEqual(result.decision_type, DecisionType.TOOL)
        self.assertEqual(result.metadata.get("tool_name"), "nuclei")
        self.assertIn("vulnerable.example", result.metadata.get("target", ""))

    def test_chat_fallback(self) -> None:
        result = ScanAwareIntentRouter().detect_intent("Explain OpenSSH risk")
        self.assertEqual(result.decision_type, DecisionType.CHAT)


class ScanOrchestratorTests(unittest.TestCase):
    def test_simulate_scan_ingests_findings(self) -> None:
        container = ScanIngestContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )
        request = ScanRequest(
            tenant_id=uuid4(),
            target="https://demo.xolaris.local",
            tool_name="nuclei",
            mode=ScanMode.SIMULATE,
            actor=ActorReference(actor_id=uuid4(), display_name="tester"),
            run_pipeline=False,
        )
        with container.session_scope(enable_pipeline=False) as svc:
            result = svc.engine.scan(request)

        self.assertIn(result.status, {ScanStatus.SUCCEEDED, ScanStatus.PARTIAL})
        self.assertGreaterEqual(result.findings_normalized, 1)
        self.assertGreaterEqual(result.findings_created, 1)
        self.assertEqual(result.mode, ScanMode.SIMULATE)


class ScanPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_simulate_with_pipeline(self) -> None:
        from trust_scoring import TrustScoringContainer
        from risk_engine import RiskEngineContainer
        from decision_service import DecisionServiceContainer
        from remediation_planner import RemediationPlannerContainer

        url = "sqlite+pysqlite:///:memory:"
        trust = TrustScoringContainer.from_url(url, create_tables=True)
        risk = RiskEngineContainer.from_url(url, create_tables=True)
        decision = DecisionServiceContainer.from_url(
            url, create_tables=True, enable_ai_stack=False
        )
        planner = RemediationPlannerContainer.from_url(url, create_tables=True)

        container = ScanIngestContainer.from_url(
            url,
            create_tables=True,
            trust_container=trust,
            risk_container=risk,
            decision_container=decision,
            planner_container=planner,
        )
        request = ScanRequest(
            tenant_id=uuid4(),
            target="https://pipeline.demo.local",
            mode=ScanMode.SIMULATE,
            actor=ActorReference(actor_id=uuid4(), display_name="pipeline-tester"),
            run_pipeline=True,
            invoke_ai_decision=False,
        )
        with container.session_scope(enable_pipeline=True) as svc:
            result = await svc.engine.scan_async(request)

        self.assertGreaterEqual(result.findings_created, 1)
        self.assertTrue(result.pipeline)
        # At least one finding should have trust + risk scored.
        scored = [p for p in result.pipeline if p.trust_score is not None]
        self.assertTrue(scored, msg=f"pipeline={result.pipeline} errors={result.errors}")


if __name__ == "__main__":
    unittest.main()
