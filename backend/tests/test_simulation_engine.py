"""Unit tests for Enterprise Simulation Engine (SQLite)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from simulation_engine import (
    SimulationEngineContainer,
    SimulationEngineService,
    SimulationOutcome,
    SimulationRequest,
)
from simulation_engine.domain.inputs import (
    AssetSimulationInput,
    PlanStepSnapshot,
    PolicySimulationInput,
    RemediationPlanSnapshot,
    RiskSimulationInput,
    RollbackStepSnapshot,
    ThreatIntelSimulationInput,
)
from simulation_engine.exceptions import (
    InvalidSimulationRequestError,
    SimulationNotFoundError,
)
from simulation_engine.query.filters import SimulationSearchFilter
from simulation_engine.query.pagination import PageRequest


def _request(**overrides) -> SimulationRequest:
    plan_id = overrides.pop("plan_id", uuid4())
    tenant_id = overrides.pop("tenant_id", uuid4())
    finding_id = overrides.pop("finding_id", uuid4())
    decision_id = overrides.pop("decision_id", uuid4())
    asset_id = overrides.pop("asset_id", uuid4())
    step_id = uuid4()
    rb_id = uuid4()

    plan = overrides.pop(
        "plan",
        RemediationPlanSnapshot(
            plan_id=plan_id,
            tenant_id=tenant_id,
            finding_id=finding_id,
            decision_id=decision_id,
            asset_id=asset_id,
            execution_type="package_upgrade",
            priority="p1",
            summary="Upgrade vulnerable package",
            steps=[
                PlanStepSnapshot(
                    step_id=step_id,
                    sequence=1,
                    action="Upgrade package openssh",
                    target="prod-web-01",
                    execution_type="package_upgrade",
                    is_destructive=False,
                    estimated_duration_seconds=120,
                )
            ],
            rollback_steps=[
                RollbackStepSnapshot(
                    step_id=rb_id,
                    sequence=1,
                    action="Downgrade package openssh",
                    target="prod-web-01",
                    estimated_duration_seconds=90,
                )
            ],
            rollback_automatic=False,
            planned_downtime_seconds=120,
            change_window_required=True,
            approval_required=True,
            estimated_risk_reduction=0.65,
        ),
    )
    data = {
        "plan": plan,
        "risk": overrides.pop(
            "risk",
            RiskSimulationInput(
                enterprise_risk_score=88.0,
                risk_level="high",
                business_impact=0.8,
                technical_impact=0.85,
                compliance_impact=0.6,
            ),
        ),
        "asset": overrides.pop(
            "asset",
            AssetSimulationInput(
                asset_id=asset_id,
                hostname="prod-web-01",
                environment="production",
                criticality=0.9,
                internet_facing=True,
                dependent_asset_ids=[uuid4()],
                dependent_services=["api-gateway"],
                compliance_tags=["pci"],
            ),
        ),
        "threat_intel": overrides.pop(
            "threat_intel",
            ThreatIntelSimulationInput(
                in_cisa_kev=True,
                actively_exploited=True,
                epss_score=0.8,
            ),
        ),
        "policy": overrides.pop(
            "policy",
            PolicySimulationInput(
                policy_version="1.0.0",
                require_simulation=True,
                require_approval=True,
                require_change_window=True,
                deny_without_rollback=True,
            ),
        ),
    }
    data.update(overrides)
    return SimulationRequest(**data)


class SimulationEngineDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.simulation_id = uuid4()
        self.service = SimulationEngineService(MagicMock())

    def test_compute_is_deterministic(self) -> None:
        req = _request()
        a = self.service.compute(req, simulation_id=self.simulation_id)
        b = self.service.compute(req, simulation_id=self.simulation_id)
        self.assertEqual(a.outcome, b.outcome)
        self.assertEqual(a.safe_to_execute, b.safe_to_execute)
        self.assertEqual(a.confidence_score, b.confidence_score)
        self.assertEqual(a.summary, b.summary)
        self.assertEqual(a.impact.downtime.seconds, b.impact.downtime.seconds)
        self.assertEqual(a.impact.blast_radius.tier, b.impact.blast_radius.tier)
        self.assertEqual(
            [(s.sequence, s.status, s.action) for s in a.steps],
            [(s.sequence, s.status, s.action) for s in b.steps],
        )

    def test_outputs_present(self) -> None:
        result = self.service.compute(_request())
        self.assertIn(result.outcome, list(SimulationOutcome))
        self.assertIsInstance(result.safe_to_execute, bool)
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertTrue(result.summary)
        self.assertTrue(result.affected_assets)
        self.assertTrue(result.impact.rollback.rollback_possible)
        self.assertGreaterEqual(result.impact.risk_reduction.reduction_ratio, 0.0)

    def test_canonical_export(self) -> None:
        result = self.service.compute(_request())
        canonical = result.to_canonical_simulation_object()
        self.assertEqual(canonical.id, result.id)
        self.assertEqual(canonical.simulator, "xolaris.simulation_engine")
        self.assertTrue(canonical.findings)

    def test_policy_violation_marks_unsafe(self) -> None:
        asset_id = uuid4()
        req = _request(
            asset_id=asset_id,
            policy=PolicySimulationInput(
                policy_version="1.0.0",
                deny_destructive_in_production=True,
                deny_without_rollback=True,
            ),
            plan=RemediationPlanSnapshot(
                plan_id=uuid4(),
                tenant_id=uuid4(),
                finding_id=uuid4(),
                decision_id=uuid4(),
                asset_id=asset_id,
                execution_type="configuration_change",
                summary="Destructive config change",
                steps=[
                    PlanStepSnapshot(
                        step_id=uuid4(),
                        sequence=1,
                        action="Wipe firewall rules",
                        target="prod-fw-01",
                        is_destructive=True,
                        estimated_duration_seconds=60,
                    )
                ],
                rollback_steps=[],
                change_window_required=False,
            ),
            asset=AssetSimulationInput(
                asset_id=asset_id,
                environment="production",
                criticality=0.95,
            ),
        )
        result = self.service.compute(req)
        self.assertEqual(result.outcome, SimulationOutcome.UNSAFE)
        self.assertFalse(result.safe_to_execute)
        self.assertTrue(result.policy_violations)

    def test_asset_mismatch(self) -> None:
        req = _request(asset=AssetSimulationInput(asset_id=uuid4(), criticality=0.5))
        with self.assertRaises(InvalidSimulationRequestError):
            self.service.simulate(req, persist=False)


class SimulationEnginePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = SimulationEngineContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )

    def test_simulate_persist_and_reload(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = svc.engine.simulate(req)
            loaded = svc.engine.get(result.id, result.tenant_id)
            self.assertEqual(loaded.id, result.id)
            self.assertEqual(loaded.outcome, result.outcome)
            self.assertEqual(loaded.safe_to_execute, result.safe_to_execute)
            by_plan = svc.engine.find_by_plan(result.plan_id, result.tenant_id)
            self.assertIsNotNone(by_plan)
            assert by_plan is not None
            self.assertEqual(by_plan.id, result.id)
            versions = svc.engine.list_versions(result.id, result.tenant_id)
            self.assertEqual(len(versions), 1)

    def test_tenant_isolation(self) -> None:
        req = _request()
        other_tenant = uuid4()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = svc.engine.simulate(req)
            with self.assertRaises(SimulationNotFoundError):
                svc.engine.get(result.id, other_tenant)

    def test_search(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = svc.engine.simulate(req)
            page = svc.engine.search(
                SimulationSearchFilter(tenant_id=result.tenant_id),
                PageRequest(page=1, page_size=10),
            )
            self.assertEqual(page.total_items, 1)
            self.assertEqual(page.items[0].id, result.id)

    def test_re_simulate_versions(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            first = svc.engine.simulate(req)
            second = svc.engine.simulate(req)
            self.assertEqual(first.id, second.id)
            self.assertEqual(second.current_version, 2)
            versions = svc.engine.list_versions(second.id, second.tenant_id)
            self.assertEqual(len(versions), 2)


if __name__ == "__main__":
    unittest.main()
