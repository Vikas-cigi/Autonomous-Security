"""Unit tests for Enterprise Remediation Planner (SQLite)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from models.common import ActorReference
from models.enums import DecisionAction, Priority, RecommendedAction

from remediation_planner import (
    ExecutionType,
    RemediationPlanRequest,
    RemediationPlannerContainer,
    RemediationPlannerService,
)
from remediation_planner.domain.inputs import (
    AssetPlanInput,
    DecisionPlanInput,
    FindingPlanInput,
    PolicyPlanInput,
    RiskPlanInput,
    ThreatIntelPlanInput,
)
from remediation_planner.exceptions import (
    InvalidPlanRequestError,
    RemediationPlanNotFoundError,
    UnsupportedDecisionForPlanningError,
)
from remediation_planner.query.filters import RemediationPlanSearchFilter
from remediation_planner.query.pagination import PageRequest


def _owner() -> ActorReference:
    return ActorReference(
        actor_id=uuid4(),
        display_name="Owner",
        actor_type="user",
    )


def _request(**overrides) -> RemediationPlanRequest:
    finding_id = overrides.pop("finding_id", uuid4())
    tenant_id = overrides.pop("tenant_id", uuid4())
    asset_id = overrides.pop("asset_id", uuid4())
    decision_id = overrides.pop("decision_id", uuid4())
    data = {
        "decision": DecisionPlanInput(
            decision_id=decision_id,
            finding_id=finding_id,
            tenant_id=tenant_id,
            decision=DecisionAction.REMEDIATE,
            recommended_action=RecommendedAction.APPLY_PATCH,
            priority=Priority.P1,
            confidence=0.86,
            reason="Critical CVE on production host",
            policy_version="1.0.0",
            owner=_owner(),
        ),
        "finding": FindingPlanInput(
            finding_id=finding_id,
            tenant_id=tenant_id,
            asset_id=asset_id,
            title="OpenSSH RCE",
            severity="critical",
            finding_type="vulnerability",
            cve_ids=["CVE-2024-9999"],
            package_name="openssh",
            fixed_version="9.8p1",
        ),
        "risk": RiskPlanInput(
            enterprise_risk_score=92.0,
            risk_level="critical",
            recommended_sla="immediate",
            business_impact=0.9,
            technical_impact=0.95,
        ),
        "asset": AssetPlanInput(
            asset_id=asset_id,
            hostname="prod-web-01",
            environment="production",
            criticality=0.9,
            internet_facing=True,
            customer_facing=True,
            compliance_tags=["pci"],
        ),
        "threat_intel": ThreatIntelPlanInput(
            in_cisa_kev=True,
            actively_exploited=True,
            epss_score=0.9,
        ),
        "policy": PolicyPlanInput(
            policy_version="1.0.0",
            require_approval=True,
            require_simulation=True,
            require_change_window=True,
        ),
    }
    data.update(overrides)
    return RemediationPlanRequest(**data)


class RemediationPlannerDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan_id = uuid4()
        self.service = RemediationPlannerService(MagicMock())

    def test_compute_is_deterministic(self) -> None:
        req = _request()
        a = self.service.compute(req, plan_id=self.plan_id)
        b = self.service.compute(req, plan_id=self.plan_id)
        self.assertEqual(a.execution_type, b.execution_type)
        self.assertEqual(a.summary, b.summary)
        self.assertEqual(a.change_summary, b.change_summary)
        self.assertEqual(a.estimated_duration.total_seconds, b.estimated_duration.total_seconds)
        self.assertEqual(a.cost_estimate.band, b.cost_estimate.band)
        self.assertEqual(
            [(s.sequence, s.action, s.kind) for s in a.steps],
            [(s.sequence, s.action, s.kind) for s in b.steps],
        )

    def test_package_upgrade_when_package_present(self) -> None:
        plan = self.service.compute(_request())
        self.assertEqual(plan.execution_type, ExecutionType.PACKAGE_UPGRADE)
        self.assertGreaterEqual(len(plan.steps), 3)
        self.assertTrue(plan.rollback_plan.steps)
        self.assertTrue(plan.execution_tasks)
        self.assertTrue(plan.validation_checks)
        self.assertTrue(plan.approval_requirement.required)
        self.assertTrue(plan.change_window.required)
        self.assertIn("Planned", plan.explanation)

    def test_canonical_export(self) -> None:
        plan = self.service.compute(_request())
        canonical = plan.to_canonical_plan()
        self.assertGreaterEqual(len(canonical.steps), 1)
        self.assertEqual(canonical.steps[0].sequence, 1)
        rollback = plan.to_canonical_rollback()
        self.assertGreaterEqual(len(rollback.steps), 1)

    def test_manual_investigation_for_investigate_decision(self) -> None:
        req = _request(
            decision=DecisionPlanInput(
                decision_id=uuid4(),
                finding_id=uuid4(),
                tenant_id=uuid4(),
                decision=DecisionAction.INVESTIGATE,
                recommended_action=RecommendedAction.MANUAL_REVIEW,
                priority=Priority.P3,
                confidence=0.5,
                reason="Need more evidence",
                policy_version="1.0.0",
                owner=_owner(),
            )
        )
        # Align finding ids
        req.finding.finding_id = req.decision.finding_id
        req.finding.tenant_id = req.decision.tenant_id
        plan = self.service.compute(req)
        self.assertEqual(plan.execution_type, ExecutionType.MANUAL_INVESTIGATION)

    def test_accept_risk_not_planable(self) -> None:
        finding_id = uuid4()
        tenant_id = uuid4()
        req = _request(
            finding_id=finding_id,
            tenant_id=tenant_id,
            decision=DecisionPlanInput(
                decision_id=uuid4(),
                finding_id=finding_id,
                tenant_id=tenant_id,
                decision=DecisionAction.ACCEPT_RISK,
                recommended_action=RecommendedAction.OTHER,
                priority=Priority.P4,
                confidence=0.4,
                reason="Accepted",
                policy_version="1.0.0",
                owner=_owner(),
            ),
        )
        with self.assertRaises(UnsupportedDecisionForPlanningError):
            self.service.plan(req, persist=False)

    def test_asset_mismatch(self) -> None:
        req = _request(asset=AssetPlanInput(asset_id=uuid4(), criticality=0.5))
        with self.assertRaises(InvalidPlanRequestError):
            self.service.plan(req, persist=False)


class RemediationPlannerPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = RemediationPlannerContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )

    def test_plan_persist_and_reload(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            plan = svc.planner.plan(req, actor="tester")
            loaded = svc.planner.get_for_decision(
                req.decision.decision_id,
                req.decision.tenant_id,
            )
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.id, plan.id)
            versions = svc.plan_repository.list_versions(plan.id, plan.tenant_id)
            self.assertEqual(len(versions), 1)

    def test_replan_increments_version(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            first = svc.planner.plan(req, actor="tester")
            second = svc.planner.plan(req, actor="tester")
            self.assertEqual(first.id, second.id)
            self.assertEqual(second.current_version, 2)

    def test_tenant_isolation(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            plan = svc.planner.plan(req)
            with self.assertRaises(RemediationPlanNotFoundError):
                svc.planner.get_plan(plan.id, uuid4())

    def test_search(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            plan = svc.planner.plan(req)
            page = svc.planner.search(
                RemediationPlanSearchFilter(
                    tenant_id=req.decision.tenant_id,
                    execution_types=[plan.execution_type],
                ),
                PageRequest(),
            )
            self.assertGreaterEqual(page.total_items, 1)


if __name__ == "__main__":
    unittest.main()
