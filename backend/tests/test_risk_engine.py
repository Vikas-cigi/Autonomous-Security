"""Unit tests for Enterprise Risk Engine (SQLite)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from risk_engine import RiskEngineContainer, RiskScoringInput
from risk_engine.domain.enums import (
    BusinessContext,
    ComplianceFramework,
    RecommendedSLA,
    RiskLevel,
    RiskPriority,
)
from risk_engine.domain.inputs import (
    AssetRiskInput,
    CvssInput,
    FindingRiskBaselineInput,
    HistoricalRiskInput,
    ThreatIntelRiskInput,
    TrustRiskInput,
)
from risk_engine.domain.weights import PILLAR_WEIGHTS, risk_level_for_score
from risk_engine.exceptions import InvalidRiskInputError, RiskAssessmentNotFoundError
from risk_engine.query.filters import RiskAssessmentSearchFilter
from risk_engine.query.pagination import PageRequest
from risk_engine.services.risk_engine_service import RiskEngineService


def _finding(**overrides) -> FindingRiskBaselineInput:
    data = {
        "finding_id": uuid4(),
        "tenant_id": uuid4(),
        "asset_id": uuid4(),
        "finding_age_days": 2.0,
    }
    data.update(overrides)
    return FindingRiskBaselineInput(**data)


class RiskEngineDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tenant = uuid4()
        self.finding_id = uuid4()
        self.asset_id = uuid4()
        self.assessment_id = uuid4()

    def _rich_input(self) -> RiskScoringInput:
        return RiskScoringInput(
            finding=_finding(
                finding_id=self.finding_id,
                tenant_id=self.tenant,
                asset_id=self.asset_id,
                finding_age_days=10.0,
            ),
            trust=TrustRiskInput(trust_score=88.0, trust_level="high"),
            cvss=CvssInput(version="3.1", base_score=9.8),
            threat_intel=ThreatIntelRiskInput(
                enrichment_present=True,
                epss_score=0.9,
                in_cisa_kev=True,
                actively_exploited=True,
                mitre_technique_count=3,
                ioc_match_count=2,
                max_ioc_confidence=0.9,
            ),
            asset=AssetRiskInput(
                asset_id=self.asset_id,
                asset_criticality=0.95,
                business_criticality=0.9,
                environments=[
                    BusinessContext.PRODUCTION,
                    BusinessContext.INTERNET_FACING,
                    BusinessContext.CUSTOMER_FACING,
                ],
                internet_facing=True,
                customer_facing=True,
                compliance_tags=[ComplianceFramework.PCI, ComplianceFramework.HIPAA],
            ),
            historical=HistoricalRiskInput(prior_risk_score=80.0, sample_size=3),
            apply_historical_blend=True,
        )

    def test_weights_sum_to_one(self) -> None:
        self.assertAlmostEqual(sum(PILLAR_WEIGHTS.values()), 1.0, places=9)

    def test_risk_level_thresholds(self) -> None:
        self.assertEqual(risk_level_for_score(95), RiskLevel.CRITICAL)
        self.assertEqual(risk_level_for_score(80), RiskLevel.HIGH)
        self.assertEqual(risk_level_for_score(50), RiskLevel.MEDIUM)
        self.assertEqual(risk_level_for_score(25), RiskLevel.LOW)
        self.assertEqual(risk_level_for_score(10), RiskLevel.INFORMATIONAL)

    def test_compute_is_deterministic(self) -> None:
        service = RiskEngineService(MagicMock())
        scoring_input = self._rich_input()
        a1 = service.compute(scoring_input, assessment_id=self.assessment_id)
        a2 = service.compute(scoring_input, assessment_id=self.assessment_id)

        self.assertEqual(a1.enterprise_risk_score.value, a2.enterprise_risk_score.value)
        self.assertEqual(a1.risk_level, a2.risk_level)
        self.assertEqual(a1.priority, a2.priority)
        self.assertEqual(a1.recommended_sla, a2.recommended_sla)
        self.assertEqual(a1.explanation.summary, a2.explanation.summary)
        self.assertEqual(a1.algorithm_version, a2.algorithm_version)
        self.assertEqual(
            [(f.category, f.raw_score, f.weight) for f in a1.factors],
            [(f.category, f.raw_score, f.weight) for f in a2.factors],
        )

    def test_rich_input_scores_high(self) -> None:
        service = RiskEngineService(MagicMock())
        assessment = service.compute(self._rich_input(), assessment_id=self.assessment_id)
        self.assertGreaterEqual(assessment.enterprise_risk_score.value, 70.0)
        self.assertIn(
            assessment.risk_level,
            {RiskLevel.HIGH, RiskLevel.CRITICAL},
        )
        self.assertIn(assessment.priority, {RiskPriority.P1, RiskPriority.P2})
        self.assertIn(
            assessment.recommended_sla,
            {RecommendedSLA.IMMEDIATE, RecommendedSLA.HOURS_24},
        )
        self.assertEqual(assessment.trust_score_used, 88.0)
        self.assertTrue(assessment.factors)
        self.assertIn("Enterprise risk score=", assessment.explanation.summary)

    def test_weak_input_scores_low(self) -> None:
        service = RiskEngineService(MagicMock())
        weak = RiskScoringInput(
            finding=_finding(
                finding_id=self.finding_id,
                tenant_id=self.tenant,
                asset_id=self.asset_id,
                finding_age_days=0.0,
                severity_hint=2.0,
            ),
            trust=TrustRiskInput(trust_score=20.0, trust_level="low"),
            cvss=CvssInput(version="3.1", base_score=2.0),
            threat_intel=ThreatIntelRiskInput(enrichment_present=False),
            asset=AssetRiskInput(
                asset_id=self.asset_id,
                asset_criticality=0.2,
                business_criticality=0.2,
                environments=[BusinessContext.DEVELOPMENT],
                internet_facing=False,
                customer_facing=False,
                compliance_tags=[],
            ),
            apply_historical_blend=False,
        )
        assessment = service.compute(weak, assessment_id=self.assessment_id)
        self.assertLess(assessment.enterprise_risk_score.value, 40.0)
        self.assertIn(
            assessment.risk_level,
            {RiskLevel.LOW, RiskLevel.INFORMATIONAL, RiskLevel.MEDIUM},
        )

    def test_asset_mismatch_raises(self) -> None:
        service = RiskEngineService(MagicMock())
        bad = RiskScoringInput(
            finding=_finding(
                finding_id=self.finding_id,
                tenant_id=self.tenant,
                asset_id=self.asset_id,
            ),
            trust=TrustRiskInput(trust_score=50.0),
            asset=AssetRiskInput(asset_id=uuid4()),
        )
        with self.assertRaises(InvalidRiskInputError):
            service.score(bad, persist=False)


class RiskEnginePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = RiskEngineContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )
        self.tenant = uuid4()
        self.finding_id = uuid4()
        self.asset_id = uuid4()

    def _input(self) -> RiskScoringInput:
        return RiskScoringInput(
            finding=_finding(
                finding_id=self.finding_id,
                tenant_id=self.tenant,
                asset_id=self.asset_id,
                finding_age_days=3.0,
            ),
            trust=TrustRiskInput(trust_score=75.0),
            cvss=CvssInput(base_score=7.5),
            threat_intel=ThreatIntelRiskInput(
                enrichment_present=True,
                epss_score=0.4,
                in_cisa_kev=False,
                actively_exploited=False,
            ),
            asset=AssetRiskInput(
                asset_id=self.asset_id,
                asset_criticality=0.7,
                business_criticality=0.6,
                environments=[BusinessContext.PRODUCTION],
                internet_facing=False,
                compliance_tags=[ComplianceFramework.SOC2],
            ),
        )

    def test_score_persist_and_reload(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            assessment = svc.risk_engine.score(self._input(), actor="test")
            loaded = svc.risk_engine.get_for_finding(self.finding_id, self.tenant)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.id, assessment.id)
            self.assertEqual(
                loaded.enterprise_risk_score.value,
                assessment.enterprise_risk_score.value,
            )
            versions = svc.risk_repository.list_versions(assessment.id, self.tenant)
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0].version, 1)

    def test_rescore_increments_version(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            first = svc.risk_engine.score(self._input(), actor="test")
            second_input = self._input()
            second_input.trust.trust_score = 90.0
            second = svc.risk_engine.score(second_input, actor="test")
            self.assertEqual(first.id, second.id)
            self.assertEqual(second.current_version, 2)
            versions = svc.risk_repository.list_versions(second.id, self.tenant)
            self.assertEqual(len(versions), 2)

    def test_tenant_isolation(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            assessment = svc.risk_engine.score(self._input())
            with self.assertRaises(RiskAssessmentNotFoundError):
                svc.risk_engine.get_assessment(assessment.id, uuid4())

    def test_search_by_level(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            assessment = svc.risk_engine.score(self._input())
            page = svc.risk_engine.search(
                RiskAssessmentSearchFilter(
                    tenant_id=self.tenant,
                    risk_levels=[assessment.risk_level],
                ),
                PageRequest(page=1, page_size=10),
            )
            self.assertGreaterEqual(page.total_items, 1)
            self.assertTrue(any(item.id == assessment.id for item in page.items))


if __name__ == "__main__":
    unittest.main()
