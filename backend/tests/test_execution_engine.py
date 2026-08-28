"""Unit tests for Enterprise Execution Engine (SQLite)."""

from __future__ import annotations

import unittest
from datetime import timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from models.common import utc_now

from execution_engine import (
    ExecutionEngineContainer,
    ExecutionEngineService,
    ExecutionRequest,
    ExecutionStatus,
)
from execution_engine.domain.inputs import (
    ApprovalDecisionInput,
    AssetExecutionInput,
    DecisionExecutionInput,
    ExecutionAuthorizationInput,
    OrgPolicyExecutionInput,
    PlanStepInput,
    RemediationPlanInput,
    RollbackStepInput,
    SimulationExecutionInput,
)
from execution_engine.exceptions import (
    ExecutionNotFoundError,
    InvalidExecutionRequestError,
)
from execution_engine.query.filters import ExecutionSearchFilter
from execution_engine.query.pagination import PageRequest
from execution_engine.services.execution_validation import ExecutionValidationService
from execution_engine.services.execution_workflow import ExecutionWorkflowService
from execution_engine.services.execution_monitoring import ExecutionMonitoringService
from execution_engine.services.execution_step_executor import ExecutionStepExecutor
from execution_engine.services.rollback_service import RollbackService
from execution_engine.services.execution_coordinator import ExecutionCoordinator


def _request(**overrides) -> ExecutionRequest:
    tenant_id = overrides.pop("tenant_id", uuid4())
    plan_id = overrides.pop("plan_id", uuid4())
    approval_id = overrides.pop("approval_id", uuid4())
    auth_id = overrides.pop("authorization_id", uuid4())
    finding_id = overrides.pop("finding_id", uuid4())
    decision_id = overrides.pop("decision_id", uuid4())
    simulation_id = overrides.pop("simulation_id", uuid4())
    step_id = uuid4()
    rb_id = uuid4()

    data = {
        "authorization": overrides.pop(
            "authorization",
            ExecutionAuthorizationInput(
                authorized=True,
                authorization_id=auth_id,
                approval_id=approval_id,
                tenant_id=tenant_id,
                plan_id=plan_id,
                simulation_id=simulation_id,
                reason="approved",
            ),
        ),
        "approval": overrides.pop(
            "approval",
            ApprovalDecisionInput(
                approval_id=approval_id,
                state="approved",
                decided_by="security-manager",
            ),
        ),
        "decision": overrides.pop(
            "decision",
            DecisionExecutionInput(
                decision_id=decision_id,
                finding_id=finding_id,
                tenant_id=tenant_id,
                decision="remediate",
            ),
        ),
        "plan": overrides.pop(
            "plan",
            RemediationPlanInput(
                plan_id=plan_id,
                execution_type="package_upgrade",
                summary="Upgrade package",
                steps=[
                    PlanStepInput(
                        step_id=step_id,
                        sequence=1,
                        action="Upgrade openssh",
                        target="prod-web-01",
                        estimated_duration_seconds=30,
                        max_retries=1,
                    ),
                    PlanStepInput(
                        step_id=uuid4(),
                        sequence=2,
                        action="Restart service",
                        target="prod-web-01",
                        depends_on_sequences=[1],
                        max_retries=0,
                    ),
                ],
                rollback_steps=[
                    RollbackStepInput(
                        step_id=rb_id,
                        sequence=1,
                        action="Downgrade openssh",
                        target="prod-web-01",
                        compensates_sequence=1,
                    )
                ],
                rollback_automatic=True,
            ),
        ),
        "simulation": overrides.pop(
            "simulation",
            SimulationExecutionInput(
                simulation_id=simulation_id,
                outcome="safe",
                safe_to_execute=True,
                confidence_score=0.9,
            ),
        ),
        "asset": overrides.pop(
            "asset",
            AssetExecutionInput(
                asset_id=uuid4(),
                hostname="prod-web-01",
                environment="production",
                criticality=0.9,
            ),
        ),
        "org_policy": overrides.pop(
            "org_policy",
            OrgPolicyExecutionInput(auto_rollback_on_failure=True),
        ),
        "initiator": "soc@tenant.local",
    }
    data.update(overrides)
    return ExecutionRequest(**data)


class ExecutionEngineDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.execution_id = uuid4()
        monitoring = ExecutionMonitoringService()
        workflow = ExecutionWorkflowService()
        steps = ExecutionStepExecutor(monitoring=monitoring)
        rollback = RollbackService(monitoring=monitoring)
        coordinator = ExecutionCoordinator(
            workflow=workflow,
            step_executor=steps,
            rollback=rollback,
            monitoring=monitoring,
        )
        self.service = ExecutionEngineService(
            MagicMock(),
            validation=ExecutionValidationService(),
            workflow=workflow,
            coordinator=coordinator,
            monitoring=monitoring,
            rollback=rollback,
            step_executor=steps,
        )

    def test_create_and_run_deterministic_success(self) -> None:
        req = _request()
        a = self.service.create(req, execution_id=self.execution_id)
        # Run without persistence via coordinator directly
        a = self.service._coordinator.run(a)
        b = self.service.create(req, execution_id=self.execution_id)
        b = self.service._coordinator.run(b)
        self.assertEqual(a.status, ExecutionStatus.COMPLETED)
        self.assertEqual(b.status, ExecutionStatus.COMPLETED)
        self.assertEqual(a.metrics.succeeded_steps, b.metrics.succeeded_steps)
        self.assertEqual(
            [(s.sequence, s.status) for s in a.plan.steps],
            [(s.sequence, s.status) for s in b.plan.steps],
        )
        self.assertIsNotNone(a.verification_request)
        self.assertTrue(a.summary.success)

    def test_unauthorized_blocked(self) -> None:
        req = _request(
            authorization=ExecutionAuthorizationInput(
                authorized=False,
                authorization_id=uuid4(),
                approval_id=uuid4(),
                tenant_id=uuid4(),
                plan_id=uuid4(),
                simulation_id=uuid4(),
                reason="denied",
            )
        )
        with self.assertRaises(InvalidExecutionRequestError):
            self.service.execute(req, persist=False)

    def test_unsafe_simulation_blocked(self) -> None:
        req = _request(
            simulation=SimulationExecutionInput(
                simulation_id=uuid4(),
                outcome="unsafe",
                safe_to_execute=False,
                confidence_score=0.2,
            )
        )
        with self.assertRaises(InvalidExecutionRequestError):
            self.service.execute(req, persist=False)

    def test_force_fail_triggers_rollback(self) -> None:
        plan_id = uuid4()
        tenant_id = uuid4()
        approval_id = uuid4()
        sim_id = uuid4()
        auth_id = uuid4()
        finding_id = uuid4()
        decision_id = uuid4()
        req = _request(
            tenant_id=tenant_id,
            plan_id=plan_id,
            approval_id=approval_id,
            authorization_id=auth_id,
            finding_id=finding_id,
            decision_id=decision_id,
            simulation_id=sim_id,
            plan=RemediationPlanInput(
                plan_id=plan_id,
                execution_type="configuration_change",
                summary="Failing change",
                steps=[
                    PlanStepInput(
                        step_id=uuid4(),
                        sequence=1,
                        action="Break something",
                        target="host",
                        max_retries=0,
                        metadata={"force_fail": "true"},
                    )
                ],
                rollback_steps=[
                    RollbackStepInput(
                        step_id=uuid4(),
                        sequence=1,
                        action="Undo break",
                        target="host",
                        compensates_sequence=1,
                    )
                ],
                rollback_automatic=True,
            ),
            authorization=ExecutionAuthorizationInput(
                authorized=True,
                authorization_id=auth_id,
                approval_id=approval_id,
                tenant_id=tenant_id,
                plan_id=plan_id,
                simulation_id=sim_id,
                reason="approved",
            ),
            approval=ApprovalDecisionInput(
                approval_id=approval_id, state="approved"
            ),
            decision=DecisionExecutionInput(
                decision_id=decision_id,
                finding_id=finding_id,
                tenant_id=tenant_id,
                decision="remediate",
            ),
            simulation=SimulationExecutionInput(
                simulation_id=sim_id,
                outcome="conditional",
                safe_to_execute=True,
                confidence_score=0.7,
            ),
        )
        result = self.service.create(req)
        result = self.service._coordinator.run(result)
        self.assertEqual(result.status, ExecutionStatus.ROLLED_BACK)
        self.assertIsNotNone(result.rollback_result)
        self.assertFalse(result.summary.success)

    def test_expired_authorization(self) -> None:
        tenant_id = uuid4()
        plan_id = uuid4()
        approval_id = uuid4()
        sim_id = uuid4()
        req = _request(
            tenant_id=tenant_id,
            plan_id=plan_id,
            approval_id=approval_id,
            simulation_id=sim_id,
            authorization=ExecutionAuthorizationInput(
                authorized=True,
                authorization_id=uuid4(),
                approval_id=approval_id,
                tenant_id=tenant_id,
                plan_id=plan_id,
                simulation_id=sim_id,
                expires_at=utc_now() - timedelta(hours=1),
                reason="expired",
            ),
        )
        with self.assertRaises(InvalidExecutionRequestError):
            self.service.execute(req, persist=False)

    def test_canonical_status_mapping(self) -> None:
        result = self.service.create(_request())
        result = self.service._coordinator.run(result)
        self.assertEqual(result.to_canonical_execution_status().value, "succeeded")


class ExecutionEnginePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = ExecutionEngineContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )

    def test_execute_persist_and_reload(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = svc.engine.execute(req)
            self.assertEqual(result.status, ExecutionStatus.COMPLETED)
            loaded = svc.engine.get(result.id, result.tenant_id)
            self.assertEqual(loaded.id, result.id)
            self.assertEqual(loaded.status, ExecutionStatus.COMPLETED)
            self.assertEqual(loaded.metrics.succeeded_steps, 2)
            versions = svc.engine.list_versions(result.id, result.tenant_id)
            self.assertGreaterEqual(len(versions), 2)

    def test_tenant_isolation(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = svc.engine.execute(req)
            with self.assertRaises(ExecutionNotFoundError):
                svc.engine.get(result.id, uuid4())

    def test_search(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = svc.engine.execute(req)
            page = svc.engine.search(
                ExecutionSearchFilter(tenant_id=result.tenant_id),
                PageRequest(page=1, page_size=10),
            )
            self.assertEqual(page.total_items, 1)
            self.assertEqual(page.items[0].id, result.id)

    def test_cancel_pending(self) -> None:
        req = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            created = svc.engine.execute(req, run=False)
            self.assertEqual(created.status, ExecutionStatus.PENDING)
            cancelled = svc.engine.cancel(
                created.id, created.tenant_id, reason="Operator abort"
            )
            self.assertEqual(cancelled.status, ExecutionStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
