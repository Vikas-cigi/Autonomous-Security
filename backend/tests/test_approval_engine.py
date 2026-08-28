"""Unit tests for Enterprise Approval Engine (SQLite)."""

from __future__ import annotations

import unittest
from datetime import timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from models.common import utc_now

from approval_engine import (
    ApprovalEngineContainer,
    ApprovalEngineService,
    ApprovalState,
    ApprovalSubmitRequest,
)
from approval_engine.domain.enums import ApproverRole
from approval_engine.domain.inputs import (
    AssetApprovalInput,
    DecisionApprovalInput,
    DelegateApprovalRequest,
    EscalateApprovalRequest,
    OrgPolicyApprovalInput,
    PlanApprovalInput,
    RecordDecisionRequest,
    RiskApprovalInput,
    SimulationApprovalInput,
)
from approval_engine.exceptions import (
    ApprovalNotFoundError,
    InvalidApprovalRequestError,
)
from approval_engine.query.filters import ApprovalSearchFilter
from approval_engine.query.pagination import PageRequest


def _submit(**overrides) -> ApprovalSubmitRequest:
    plan_id = overrides.pop("plan_id", uuid4())
    tenant_id = overrides.pop("tenant_id", uuid4())
    finding_id = overrides.pop("finding_id", uuid4())
    decision_id = overrides.pop("decision_id", uuid4())
    simulation_id = overrides.pop("simulation_id", uuid4())
    asset_id = overrides.pop("asset_id", uuid4())

    data = {
        "decision": overrides.pop(
            "decision",
            DecisionApprovalInput(
                decision_id=decision_id,
                finding_id=finding_id,
                tenant_id=tenant_id,
                decision="remediate",
                priority="p1",
            ),
        ),
        "plan": overrides.pop(
            "plan",
            PlanApprovalInput(
                plan_id=plan_id,
                execution_type="package_upgrade",
                summary="Upgrade vulnerable package",
                approval_required=True,
                change_window_required=True,
            ),
        ),
        "simulation": overrides.pop(
            "simulation",
            SimulationApprovalInput(
                simulation_id=simulation_id,
                outcome="conditional",
                safe_to_execute=True,
                confidence_score=0.86,
                blast_radius="group",
                downtime_seconds=120,
            ),
        ),
        "risk": overrides.pop(
            "risk",
            RiskApprovalInput(
                enterprise_risk_score=92.0,
                risk_level="critical",
            ),
        ),
        "asset": overrides.pop(
            "asset",
            AssetApprovalInput(
                asset_id=asset_id,
                hostname="prod-web-01",
                environment="production",
                criticality=0.9,
            ),
        ),
        "org_policy": overrides.pop(
            "org_policy",
            OrgPolicyApprovalInput(auto_approve_enabled=False),
        ),
        "requester": "soc@tenant.local",
    }
    data.update(overrides)
    return ApprovalSubmitRequest(**data)


class ApprovalEngineDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.approval_id = uuid4()
        self.service = ApprovalEngineService(MagicMock())

    def test_compute_is_deterministic(self) -> None:
        req = _submit()
        a = self.service.compute(req, approval_id=self.approval_id)
        b = self.service.compute(req, approval_id=self.approval_id)
        self.assertEqual(a.state, b.state)
        self.assertEqual(a.summary, b.summary)
        self.assertEqual(a.matched_rule_names, b.matched_rule_names)
        self.assertEqual(
            [(s.sequence, s.required_role, s.approval_type) for s in a.workflow.stages],
            [(s.sequence, s.required_role, s.approval_type) for s in b.workflow.stages],
        )

    def test_critical_risk_requires_dual_control(self) -> None:
        result = self.service.compute(_submit())
        self.assertEqual(result.state, ApprovalState.PENDING)
        roles = [s.required_role for s in result.workflow.stages]
        self.assertEqual(
            roles,
            [
                ApproverRole.SECURITY_MANAGER,
                ApproverRole.INFRASTRUCTURE_MANAGER,
            ],
        )
        self.assertTrue(result.assigned_approvers)
        self.assertTrue(result.notifications)

    def test_production_firewall_policy(self) -> None:
        asset_id = uuid4()
        req = _submit(
            asset_id=asset_id,
            risk=RiskApprovalInput(
                enterprise_risk_score=55.0, risk_level="medium"
            ),
            plan=PlanApprovalInput(
                plan_id=uuid4(),
                execution_type="firewall_change",
                summary="Open temporary port",
            ),
            asset=AssetApprovalInput(
                asset_id=asset_id,
                environment="production",
                criticality=0.8,
            ),
        )
        result = self.service.compute(req)
        roles = [s.required_role for s in result.workflow.stages]
        self.assertEqual(
            roles,
            [ApproverRole.NETWORK_TEAM, ApproverRole.SECURITY_APPROVER],
        )

    def test_auto_approve_low_dev(self) -> None:
        asset_id = uuid4()
        req = _submit(
            asset_id=asset_id,
            risk=RiskApprovalInput(enterprise_risk_score=12.0, risk_level="low"),
            asset=AssetApprovalInput(
                asset_id=asset_id,
                environment="development",
                criticality=0.2,
            ),
            org_policy=OrgPolicyApprovalInput(auto_approve_enabled=True),
        )
        result = self.service.compute(req)
        self.assertEqual(result.state, ApprovalState.AUTO_APPROVED)
        self.assertTrue(result.execution_authorized)
        self.assertIsNotNone(result.decision)
        assert result.decision is not None
        self.assertTrue(result.decision.execution_authorization.authorized)

    def test_unsafe_simulation_blocked(self) -> None:
        req = _submit(
            simulation=SimulationApprovalInput(
                simulation_id=uuid4(),
                outcome="unsafe",
                safe_to_execute=False,
                confidence_score=0.4,
            )
        )
        with self.assertRaises(InvalidApprovalRequestError):
            self.service.submit(req, persist=False)

    def test_canonical_export(self) -> None:
        result = self.service.compute(
            _submit(
                risk=RiskApprovalInput(
                    enterprise_risk_score=10.0, risk_level="low"
                ),
                asset=AssetApprovalInput(
                    asset_id=uuid4(),
                    environment="development",
                    criticality=0.1,
                ),
                org_policy=OrgPolicyApprovalInput(auto_approve_enabled=True),
            )
        )
        canonical = result.to_canonical_approval_record()
        self.assertEqual(canonical.status.value, "approved")
        self.assertIsNotNone(canonical.approver)


class ApprovalEnginePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = ApprovalEngineContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )

    def test_submit_persist_and_multi_stage_approve(self) -> None:
        req = _submit()
        with self.container.session() as session:
            svc = self.container.build(session)
            approval = svc.engine.submit(req)
            self.assertEqual(approval.state, ApprovalState.PENDING)

            first = approval.workflow.stages[0]
            assignee = first.assignments[0].approver
            mid = svc.engine.record_decision(
                RecordDecisionRequest(
                    approval_id=approval.id,
                    tenant_id=approval.tenant_id,
                    approve=True,
                    approver=assignee,
                    stage_id=first.id,
                    comment="Security OK",
                )
            )
            self.assertEqual(mid.state, ApprovalState.PENDING)

            second = mid.workflow.stages[1]
            final = svc.engine.record_decision(
                RecordDecisionRequest(
                    approval_id=mid.id,
                    tenant_id=mid.tenant_id,
                    approve=True,
                    approver=second.assignments[0].approver,
                    stage_id=second.id,
                    comment="Infra OK",
                )
            )
            self.assertEqual(final.state, ApprovalState.APPROVED)
            auth = svc.engine.authorization(final.id, final.tenant_id)
            self.assertIsNotNone(auth)
            assert auth is not None
            self.assertTrue(auth.authorized)
            versions = svc.engine.list_versions(final.id, final.tenant_id)
            self.assertGreaterEqual(len(versions), 3)

    def test_reject(self) -> None:
        req = _submit()
        with self.container.session() as session:
            svc = self.container.build(session)
            approval = svc.engine.submit(req)
            stage = approval.workflow.stages[0]
            rejected = svc.engine.record_decision(
                RecordDecisionRequest(
                    approval_id=approval.id,
                    tenant_id=approval.tenant_id,
                    approve=False,
                    approver=stage.assignments[0].approver,
                    stage_id=stage.id,
                    comment="Too risky",
                )
            )
            self.assertEqual(rejected.state, ApprovalState.REJECTED)
            self.assertFalse(rejected.execution_authorized)

    def test_tenant_isolation(self) -> None:
        req = _submit()
        with self.container.session() as session:
            svc = self.container.build(session)
            approval = svc.engine.submit(req)
            with self.assertRaises(ApprovalNotFoundError):
                svc.engine.get(approval.id, uuid4())

    def test_search_and_expire(self) -> None:
        req = _submit(
            org_policy=OrgPolicyApprovalInput(
                auto_approve_enabled=False,
                default_expiration_hours=1,
            )
        )
        with self.container.session() as session:
            svc = self.container.build(session)
            approval = svc.engine.submit(req)
            page = svc.engine.search(
                ApprovalSearchFilter(tenant_id=approval.tenant_id),
                PageRequest(page=1, page_size=10),
            )
            self.assertEqual(page.total_items, 1)
            expired = svc.engine.expire_if_needed(
                approval.id,
                approval.tenant_id,
                now=utc_now() + timedelta(hours=2),
            )
            self.assertEqual(expired.state, ApprovalState.EXPIRED)

    def test_delegate_and_escalate(self) -> None:
        req = _submit()
        with self.container.session() as session:
            svc = self.container.build(session)
            approval = svc.engine.submit(req)
            assignment = approval.workflow.stages[0].assignments[0]
            delegated = svc.engine.delegate(
                DelegateApprovalRequest(
                    approval_id=approval.id,
                    tenant_id=approval.tenant_id,
                    assignment_id=assignment.id,
                    from_approver=assignment.approver,
                    to_approver="delegate-user@tenant.local",
                    reason="On PTO",
                )
            )
            self.assertIn("delegate-user@tenant.local", delegated.assigned_approvers)
            escalated = svc.engine.escalate(
                EscalateApprovalRequest(
                    approval_id=approval.id,
                    tenant_id=approval.tenant_id,
                    reason="SLA breach",
                )
            )
            self.assertEqual(escalated.state, ApprovalState.ESCALATED)
            self.assertTrue(escalated.workflow.escalated)


if __name__ == "__main__":
    unittest.main()
