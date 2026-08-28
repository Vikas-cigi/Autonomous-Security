"""Unit tests for Enterprise Verification Engine (SQLite)."""

from __future__ import annotations

import unittest
from uuid import uuid4

from models.common import utc_now
from models.enums import VerificationStatus as CanonicalVerificationStatus

from verification_engine import (
    ClosureRecommendation,
    VerificationEngineContainer,
    VerificationRequest,
    VerificationStatus,
)
from verification_engine.domain.inputs import (
    AssetVerificationInput,
    DecisionVerificationInput,
    EvidenceItemInput,
    ExecutionVerificationInput,
    FindingVerificationInput,
    OrgPolicyVerificationInput,
    PlanVerificationInput,
    RescanResultInput,
    RiskSnapshotInput,
)
from verification_engine.exceptions import (
    InvalidVerificationRequestError,
    VerificationNotFoundError,
)
from verification_engine.query.filters import VerificationSearchFilter
from verification_engine.query.pagination import PageRequest


def _request(**overrides) -> VerificationRequest:
    tenant_id = overrides.pop("tenant_id", uuid4())
    finding_id = overrides.pop("finding_id", uuid4())
    decision_id = overrides.pop("decision_id", uuid4())
    plan_id = overrides.pop("plan_id", uuid4())
    execution_id = overrides.pop("execution_id", uuid4())
    asset_id = overrides.pop("asset_id", uuid4())

    data = {
        "execution": overrides.pop(
            "execution",
            ExecutionVerificationInput(
                execution_id=execution_id,
                execution_status="completed",
                success=True,
                succeeded_step_count=2,
                failed_step_count=0,
                rolled_back=False,
                summary="Completed successfully",
            ),
        ),
        "plan": overrides.pop(
            "plan",
            PlanVerificationInput(
                plan_id=plan_id,
                execution_type="package_upgrade",
                summary="Upgrade package",
                expected_outcomes=["CVE mitigated"],
                step_count=2,
            ),
        ),
        "decision": overrides.pop(
            "decision",
            DecisionVerificationInput(
                decision_id=decision_id,
                finding_id=finding_id,
                tenant_id=tenant_id,
                decision="remediate",
                recommended_action="upgrade_package",
            ),
        ),
        "finding": overrides.pop(
            "finding",
            FindingVerificationInput(
                finding_id=finding_id,
                title="OpenSSH CVE",
                severity="high",
                status="open",
                asset_id=asset_id,
            ),
        ),
        "pre_evidence": overrides.pop(
            "pre_evidence",
            [
                EvidenceItemInput(
                    summary="CVE present on host",
                    kind="scan",
                    indicates_resolved=False,
                )
            ],
        ),
        "post_evidence": overrides.pop(
            "post_evidence",
            [
                EvidenceItemInput(
                    summary="Package upgraded",
                    kind="configuration",
                    indicates_resolved=True,
                    attributes={"configuration_validated": "true"},
                ),
                EvidenceItemInput(
                    summary="Service healthy",
                    kind="availability",
                    attributes={"service_up": "true"},
                ),
            ],
        ),
        "asset": overrides.pop(
            "asset",
            AssetVerificationInput(
                asset_id=asset_id,
                hostname="prod-web-01",
                environment="production",
                criticality=0.8,
                compliance_tags=["pci"],
                service_expected_up=True,
            ),
        ),
        "risk": overrides.pop(
            "risk",
            RiskSnapshotInput(
                pre_risk_score=80.0,
                post_risk_score=20.0,
                risk_level="high",
            ),
        ),
        "org_policy": overrides.pop(
            "org_policy",
            OrgPolicyVerificationInput(
                require_rescan=True,
                require_compliance_check=True,
                require_service_check=True,
                min_risk_reduction_ratio=0.1,
                auto_close_on_verify=True,
                escalate_on_rollback=True,
            ),
        ),
        "rescan": overrides.pop(
            "rescan",
            RescanResultInput(
                performed=True,
                finding_still_present=False,
                scanner="nessus",
                summary="Finding cleared",
            ),
        ),
        "operator": overrides.pop("operator", "verification-bot"),
        "actor": overrides.pop("actor", "system"),
        "evaluated_at": overrides.pop("evaluated_at", utc_now()),
    }
    data.update(overrides)
    return VerificationRequest(**data)


class VerificationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = VerificationEngineContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )

    def test_verify_success_closes_finding(self) -> None:
        request = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            result = svc.engine.verify(request)

            self.assertEqual(result.status, VerificationStatus.VERIFIED)
            self.assertEqual(
                result.closure_recommendation, ClosureRecommendation.CLOSE_FINDING
            )
            self.assertIsNotNone(result.summary)
            self.assertIsNotNone(result.report)
            self.assertIsNotNone(result.comparison)
            self.assertGreater(len(result.checks), 0)
            self.assertTrue(result.summary.success)

            canonical = result.to_canonical_verification_object()
            self.assertEqual(canonical.status, CanonicalVerificationStatus.PASSED)
            self.assertEqual(canonical.finding_id, request.finding.finding_id)

            loaded = svc.engine.get(result.id, result.tenant_id)
            self.assertEqual(loaded.status, VerificationStatus.VERIFIED)

            page = svc.engine.search(
                VerificationSearchFilter(tenant_id=result.tenant_id),
                PageRequest(page=1, page_size=10),
            )
            self.assertEqual(page.total_items, 1)

            versions = svc.engine.list_versions(result.id, result.tenant_id)
            self.assertGreaterEqual(len(versions), 2)

            evidence = svc.evidence_repository.list_for_verification(
                result.id, result.tenant_id
            )
            self.assertGreaterEqual(len(evidence), 2)

    def test_finding_still_present_reopens(self) -> None:
        request = _request(
            rescan=RescanResultInput(
                performed=True,
                finding_still_present=True,
                summary="CVE still present",
            ),
            post_evidence=[
                EvidenceItemInput(
                    summary="Still vulnerable",
                    kind="scan",
                    indicates_resolved=False,
                )
            ],
        )
        with self.container.session() as session:
            svc = self.container.build(session)
            result = svc.engine.verify(request)
            self.assertEqual(result.status, VerificationStatus.REOPENED)
            self.assertEqual(
                result.closure_recommendation, ClosureRecommendation.REOPEN_FINDING
            )
            self.assertEqual(result.finding.disposition.value, "reopen")

    def test_rollback_escalates(self) -> None:
        request = _request(
            execution=ExecutionVerificationInput(
                execution_id=uuid4(),
                execution_status="rolled_back",
                success=False,
                succeeded_step_count=0,
                failed_step_count=1,
                rolled_back=True,
                summary="Rolled back",
            ),
            rescan=RescanResultInput(
                performed=True,
                finding_still_present=True,
                summary="Still open after rollback",
            ),
        )
        with self.container.session() as session:
            svc = self.container.build(session)
            result = svc.engine.verify(request)
            self.assertEqual(result.status, VerificationStatus.ESCALATED)
            self.assertEqual(
                result.closure_recommendation,
                ClosureRecommendation.ESCALATE_FINDING,
            )

    def test_mismatch_finding_ids_rejected(self) -> None:
        request = _request()
        request.decision.finding_id = uuid4()
        with self.container.session() as session:
            svc = self.container.build(session)
            with self.assertRaises(InvalidVerificationRequestError):
                svc.engine.verify(request)

    def test_not_found(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            with self.assertRaises(VerificationNotFoundError):
                svc.engine.get(uuid4(), uuid4())

    def test_replay_versions(self) -> None:
        request = _request()
        with self.container.session() as session:
            svc = self.container.build(session)
            first = svc.engine.verify(request)
            replay_req = _request(
                tenant_id=first.tenant_id,
                finding_id=first.finding_id,
                decision_id=first.decision_id,
                plan_id=first.plan_id,
                execution_id=first.execution_id,
            )
            second = svc.engine.replay(
                first.id, first.tenant_id, replay_req, actor="auditor"
            )
            self.assertEqual(second.id, first.id)
            self.assertEqual(second.status, VerificationStatus.VERIFIED)
            versions = svc.engine.list_versions(first.id, first.tenant_id)
            self.assertGreaterEqual(len(versions), 3)


if __name__ == "__main__":
    unittest.main()
