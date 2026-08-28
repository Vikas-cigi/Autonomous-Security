"""Unit tests for Enterprise Decision Service (SQLite + fake AI gateway)."""

from __future__ import annotations

import asyncio
import unittest
from typing import Optional
from uuid import uuid4

from models.common import ActorReference
from models.enums import DecisionAction, Priority

from decision_service import (
    DecisionLifecycleStatus,
    DecisionRequest,
    DecisionServiceContainer,
    SecurityDecisionType,
)
from decision_service.domain.inputs import (
    AssetSnapshot,
    EvidenceSnapshot,
    FindingSnapshot,
    PolicySnapshot,
    RiskSnapshot,
    ThreatIntelSnapshot,
    TrustSnapshot,
)
from decision_service.domain.models import (
    AIRequestEnvelope,
    AIResponseEnvelope,
    DecisionContext,
)
from decision_service.exceptions import InvalidDecisionRequestError
from decision_service.interfaces.ai_gateway import AIDecisionGateway
from decision_service.query.filters import DecisionSearchFilter
from decision_service.query.pagination import PageRequest
from decision_service.services.decision_service import DecisionService
from decision_service.services.deterministic_advisor import DeterministicDecisionAdvisor
from decision_service.persistence.decision_repository import PostgresDecisionRepository
from decision_service.services.audit_service import DecisionAuditService
from decision_service.persistence.decision_audit_repository import (
    PostgresDecisionAuditRepository,
)


class FakeAIGateway(AIDecisionGateway):
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    async def invoke(
        self,
        context: DecisionContext,
        *,
        session_id: Optional[str] = None,
        provider_name: Optional[str] = None,
    ):
        self.calls += 1
        req = AIRequestEnvelope(
            session_id=session_id,
            provider_name=provider_name or "fake",
            user_message=context.operator_message,
        )
        resp = AIResponseEnvelope(
            provider="fake",
            model="fake-model",
            text=self.text,
            latency_ms=1.0,
        )
        return req, resp


def _owner() -> ActorReference:
    return ActorReference(
        actor_id=uuid4(),
        display_name="Decision Owner",
        actor_type="user",
    )


def _approver() -> ActorReference:
    return ActorReference(
        actor_id=uuid4(),
        display_name="Decision Approver",
        actor_type="user",
    )


def _request(**overrides) -> DecisionRequest:
    finding_id = overrides.pop("finding_id", uuid4())
    tenant_id = overrides.pop("tenant_id", uuid4())
    asset_id = overrides.pop("asset_id", uuid4())
    data = {
        "finding": FindingSnapshot(
            finding_id=finding_id,
            tenant_id=tenant_id,
            asset_id=asset_id,
            title="Critical RCE",
            severity="critical",
            cve_ids=["CVE-2024-0001"],
        ),
        "trust": TrustSnapshot(
            trust_score=85.0,
            trust_level="high",
            recommendation_confidence="act",
        ),
        "risk": RiskSnapshot(
            enterprise_risk_score=92.0,
            risk_level="critical",
            priority="p1",
            recommended_sla="immediate",
        ),
        "owner": _owner(),
        "approver": _approver(),
        "threat_intel": ThreatIntelSnapshot(
            enrichment_present=True,
            in_cisa_kev=True,
            actively_exploited=True,
            epss_score=0.9,
            mitre_technique_count=2,
            ioc_match_count=1,
        ),
        "asset": AssetSnapshot(
            asset_id=asset_id,
            environment="production",
            criticality=0.9,
            internet_facing=True,
            customer_facing=True,
            compliance_tags=["pci"],
        ),
        "evidence": EvidenceSnapshot(
            evidence_ids=[uuid4()],
            evidence_count=1,
            validated_count=1,
            average_confidence=0.9,
            highlights=["hash-verified artifact"],
        ),
        "policy": PolicySnapshot(
            policy_version="1.0.0",
            precomputed_verdict="allow",
        ),
        "invoke_ai": False,
    }
    data.update(overrides)
    return DecisionRequest(**data)


def _run(coro):
    return asyncio.run(coro)


class DeterministicAdvisorTests(unittest.TestCase):
    def test_high_risk_high_trust_remediates(self) -> None:
        from decision_service.services.context_assembler import DecisionContextAssembler

        ctx = DecisionContextAssembler().assemble(_request())
        rec = DeterministicDecisionAdvisor().recommend(ctx)
        self.assertEqual(rec.decision_type, SecurityDecisionType.REMEDIATE)
        self.assertGreaterEqual(rec.confidence, 0.5)

    def test_low_trust_investigates(self) -> None:
        from decision_service.services.context_assembler import DecisionContextAssembler

        req = _request(trust=TrustSnapshot(trust_score=20.0, trust_level="low"))
        ctx = DecisionContextAssembler().assemble(req)
        rec = DeterministicDecisionAdvisor().recommend(ctx)
        self.assertEqual(rec.decision_type, SecurityDecisionType.INVESTIGATE)


class DecisionServiceOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = DecisionServiceContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
            enable_ai_stack=False,
        )

    def test_deterministic_decide_persists(self) -> None:
        req = _request()
        with self.container.session() as session:
            bundle = self.container.build(session)
            response = _run(bundle.decision.decide(req, actor="tester"))
            self.assertEqual(response.status, DecisionLifecycleStatus.FINALIZED)
            self.assertEqual(
                response.decision_object.decision,
                DecisionAction.REMEDIATE,
            )
            self.assertIn(response.decision_object.priority, {Priority.P0, Priority.P1})
            loaded = bundle.decision.get_for_finding(
                req.finding.finding_id,
                req.finding.tenant_id,
            )
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.id, response.id)
            versions = bundle.decision_repository.list_versions(
                response.id,
                response.tenant_id,
            )
            self.assertEqual(len(versions), 1)

    def test_ai_json_recommendation(self) -> None:
        fake = FakeAIGateway(
            text=(
                '{"decision_type":"investigate","confidence":0.77,'
                '"recommended_action":"manual_review",'
                '"next_step":"Gather more evidence",'
                '"business_justification":"Unclear business blast radius",'
                '"technical_justification":"Trust signals conflict",'
                '"explanation":"Need corroboration"}'
            )
        )
        container = DecisionServiceContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
            ai_gateway=fake,
            enable_ai_stack=True,
        )
        req = _request(invoke_ai=True)
        with container.session() as session:
            bundle = container.build(session)
            response = _run(bundle.decision.decide(req))
            self.assertEqual(fake.calls, 1)
            self.assertEqual(
                response.recommendation.decision_type,
                SecurityDecisionType.INVESTIGATE,
            )
            self.assertAlmostEqual(response.recommendation.confidence, 0.77, places=2)
            self.assertIsNotNone(response.ai_request)
            self.assertIsNotNone(response.ai_response)
            self.assertIn("Decision=", response.explanation.summary)

    def test_asset_mismatch_raises(self) -> None:
        req = _request(
            asset=AssetSnapshot(asset_id=uuid4(), criticality=0.5),
        )
        with self.container.session() as session:
            bundle = self.container.build(session)
            with self.assertRaises(InvalidDecisionRequestError):
                _run(bundle.decision.decide(req, persist=False))

    def test_missing_approver_downgrades_p0_remediate(self) -> None:
        req = _request(approver=None)
        with self.container.session() as session:
            bundle = self.container.build(session)
            response = _run(bundle.decision.decide(req, persist=False))
            # Without approver, P0/P1 remediate must escalate for DecisionObject validity
            self.assertEqual(
                response.recommendation.decision_type,
                SecurityDecisionType.ESCALATE,
            )
            self.assertEqual(
                response.decision_object.decision,
                DecisionAction.ESCALATE,
            )

    def test_policy_deny_status(self) -> None:
        req = _request(
            policy=PolicySnapshot(
                policy_version="1.0.0",
                precomputed_verdict="deny",
                precomputed_reason="Blocked by change freeze",
            )
        )
        with self.container.session() as session:
            bundle = self.container.build(session)
            response = _run(bundle.decision.decide(req))
            self.assertEqual(response.status, DecisionLifecycleStatus.POLICY_DENIED)
            self.assertEqual(response.policy_verdict, "deny")

    def test_search_and_tenant_isolation(self) -> None:
        req = _request()
        with self.container.session() as session:
            bundle = self.container.build(session)
            response = _run(bundle.decision.decide(req))
            page = bundle.decision.search(
                DecisionSearchFilter(tenant_id=req.finding.tenant_id),
                PageRequest(),
            )
            self.assertGreaterEqual(page.total_items, 1)
            other = DecisionService(
                PostgresDecisionRepository(session),
                audit_service=DecisionAuditService(
                    PostgresDecisionAuditRepository(session)
                ),
            )
            from decision_service.exceptions import DecisionNotFoundError

            with self.assertRaises(DecisionNotFoundError):
                other.get_decision(response.id, uuid4())


if __name__ == "__main__":
    unittest.main()
