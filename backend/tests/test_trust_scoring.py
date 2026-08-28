"""Unit tests for Enterprise Trust Scoring Engine (SQLite)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from models.enums import EvidenceValidationStatus, SourceTool
from trust_scoring import TrustScoringContainer, TrustScoringInput
from trust_scoring.domain.enums import (
    CrossValidationStatus,
    RecommendationConfidence,
    TrustLevel,
)
from trust_scoring.domain.inputs import (
    AssetConfidenceInput,
    CorrelationSignalInput,
    EvidenceItemInput,
    FindingBaselineInput,
    HistoricalSignalInput,
    IOCConfidenceInput,
    ScannerObservationInput,
    ThreatIntelConfidenceInput,
)
from trust_scoring.domain.weights import COMPONENT_WEIGHTS, trust_level_for_score
from trust_scoring.exceptions import InvalidScoringInputError, TrustAssessmentNotFoundError
from trust_scoring.query.filters import TrustAssessmentSearchFilter
from trust_scoring.query.pagination import PageRequest
from trust_scoring.services.trust_scoring_service import TrustScoringService


def _baseline(**overrides) -> FindingBaselineInput:
    data = {
        "finding_id": uuid4(),
        "tenant_id": uuid4(),
        "asset_id": uuid4(),
        "source_tool": SourceTool.NESSUS,
        "finding_confidence": 0.8,
        "evidence_count": 1,
        "has_cve": True,
        "finding_age_days": 2.0,
    }
    data.update(overrides)
    return FindingBaselineInput(**data)


class TrustScoringDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tenant = uuid4()
        self.finding_id = uuid4()
        self.asset_id = uuid4()
        self.assessment_id = uuid4()

    def _rich_input(self) -> TrustScoringInput:
        return TrustScoringInput(
            finding=_baseline(
                finding_id=self.finding_id,
                tenant_id=self.tenant,
                asset_id=self.asset_id,
                finding_confidence=0.85,
                evidence_count=3,
                has_cve=True,
                has_cwe=True,
                has_mitre=True,
                finding_age_days=1.0,
            ),
            evidence_items=[
                EvidenceItemInput(
                    validation_status=EvidenceValidationStatus.VALIDATED,
                    confidence=0.95,
                    has_content_hash=True,
                    has_lineage=True,
                ),
                EvidenceItemInput(
                    validation_status=EvidenceValidationStatus.VALIDATED,
                    confidence=0.9,
                    has_content_hash=True,
                    has_lineage=True,
                ),
            ],
            scanner_observations=[
                ScannerObservationInput(
                    source_tool=SourceTool.NESSUS,
                    scanner_confidence=0.9,
                    severity_agrees=True,
                    title_similarity=1.0,
                ),
                ScannerObservationInput(
                    source_tool=SourceTool.QUALYS,
                    scanner_confidence=0.85,
                    severity_agrees=True,
                    title_similarity=0.9,
                ),
            ],
            asset=AssetConfidenceInput(
                asset_id=self.asset_id,
                inventory_confidence=0.9,
                ownership_known=True,
                environment_known=True,
                criticality_score=0.8,
                last_seen_days_ago=1.0,
            ),
            threat_intel=ThreatIntelConfidenceInput(
                enrichment_present=True,
                intel_confidence=0.9,
                cve_match_count=1,
                in_cisa_kev=True,
                actively_exploited=True,
                epss_score=0.9,
                mitre_technique_count=2,
            ),
            ioc=IOCConfidenceInput(
                matched_ioc_count=2,
                max_ioc_confidence=0.85,
                active_ioc_count=2,
            ),
            historical=HistoricalSignalInput(
                prior_true_positive_rate=0.85,
                prior_false_positive_rate=0.1,
                sample_size=50,
                scanner_historical_accuracy=0.88,
                days_since_last_similar=5.0,
            ),
            correlation=CorrelationSignalInput(
                correlated_finding_count=3,
                duplicate_count=2,
                severity_consistency=1.0,
                type_consistency=1.0,
                asset_consistency=1.0,
                conflicting_status=False,
            ),
            apply_time_decay=True,
        )

    def test_weights_sum_to_one(self) -> None:
        self.assertAlmostEqual(sum(COMPONENT_WEIGHTS.values()), 1.0, places=9)

    def test_trust_level_thresholds(self) -> None:
        self.assertEqual(trust_level_for_score(95), TrustLevel.VERY_HIGH)
        self.assertEqual(trust_level_for_score(80), TrustLevel.HIGH)
        self.assertEqual(trust_level_for_score(55), TrustLevel.MEDIUM)
        self.assertEqual(trust_level_for_score(30), TrustLevel.LOW)
        self.assertEqual(trust_level_for_score(10), TrustLevel.VERY_LOW)

    def test_compute_is_deterministic(self) -> None:
        service = TrustScoringService(MagicMock())
        scoring_input = self._rich_input()
        a1 = service.compute(scoring_input, assessment_id=self.assessment_id)
        a2 = service.compute(scoring_input, assessment_id=self.assessment_id)

        self.assertEqual(a1.trust_score.value, a2.trust_score.value)
        self.assertEqual(a1.confidence_level, a2.confidence_level)
        self.assertEqual(a1.recommendation_confidence, a2.recommendation_confidence)
        self.assertEqual(a1.confidence_explanation, a2.confidence_explanation)
        self.assertEqual(a1.algorithm_version, a2.algorithm_version)
        self.assertEqual(
            [(f.category, f.raw_score, f.weight) for f in a1.supporting_factors],
            [(f.category, f.raw_score, f.weight) for f in a2.supporting_factors],
        )
        self.assertEqual(
            [(f.category, f.raw_score, f.weight) for f in a1.negative_factors],
            [(f.category, f.raw_score, f.weight) for f in a2.negative_factors],
        )

    def test_rich_input_scores_high(self) -> None:
        service = TrustScoringService(MagicMock())
        assessment = service.compute(self._rich_input(), assessment_id=self.assessment_id)
        self.assertGreaterEqual(assessment.trust_score.value, 70.0)
        self.assertIn(
            assessment.confidence_level,
            {TrustLevel.HIGH, TrustLevel.VERY_HIGH},
        )
        self.assertEqual(
            assessment.recommendation_confidence,
            RecommendationConfidence.ACT,
        )
        self.assertIsNotNone(assessment.evidence_quality)
        self.assertIsNotNone(assessment.cross_validation)
        self.assertEqual(
            assessment.cross_validation.status,
            CrossValidationStatus.CONFIRMED,
        )
        self.assertTrue(assessment.supporting_factors)
        self.assertIn("Overall trust score=", assessment.confidence_explanation)

    def test_weak_input_scores_low(self) -> None:
        service = TrustScoringService(MagicMock())
        weak = TrustScoringInput(
            finding=_baseline(
                finding_id=self.finding_id,
                tenant_id=self.tenant,
                asset_id=self.asset_id,
                finding_confidence=0.2,
                evidence_count=0,
                has_cve=False,
                finding_age_days=400.0,
            ),
            evidence_items=[],
            scanner_observations=[],
            apply_time_decay=True,
        )
        assessment = service.compute(weak, assessment_id=self.assessment_id)
        self.assertLess(assessment.trust_score.value, 55.0)
        self.assertLess(assessment.trust_score.time_decay_multiplier, 1.0)
        self.assertIn(
            assessment.recommendation_confidence,
            {
                RecommendationConfidence.INVESTIGATE,
                RecommendationConfidence.DEFER,
                RecommendationConfidence.DISCARD,
            },
        )

    def test_asset_id_mismatch_rejected(self) -> None:
        service = TrustScoringService(MagicMock())
        bad = TrustScoringInput(
            finding=_baseline(
                finding_id=self.finding_id,
                tenant_id=self.tenant,
                asset_id=self.asset_id,
            ),
            asset=AssetConfidenceInput(asset_id=uuid4()),
        )
        with self.assertRaises(InvalidScoringInputError):
            service.score(bad, persist=False)


class TrustScoringPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = TrustScoringContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )
        self.tenant = uuid4()
        self.finding_id = uuid4()
        self.asset_id = uuid4()

    def _input(self) -> TrustScoringInput:
        return TrustScoringInput(
            finding=_baseline(
                finding_id=self.finding_id,
                tenant_id=self.tenant,
                asset_id=self.asset_id,
            ),
            evidence_items=[
                EvidenceItemInput(
                    validation_status=EvidenceValidationStatus.VALIDATED,
                    confidence=0.8,
                    has_content_hash=True,
                    has_lineage=True,
                )
            ],
            scanner_observations=[
                ScannerObservationInput(
                    source_tool=SourceTool.NESSUS,
                    scanner_confidence=0.75,
                )
            ],
            asset=AssetConfidenceInput(
                asset_id=self.asset_id,
                inventory_confidence=0.7,
                ownership_known=True,
            ),
        )

    def test_score_persist_and_retrieve(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            assessment = svc.scoring.score(self._input(), actor="test")
            self.assertEqual(assessment.finding_id, self.finding_id)
            self.assertEqual(assessment.tenant_id, self.tenant)
            self.assertGreaterEqual(assessment.current_version, 1)

            loaded = svc.scoring.get_for_finding(self.finding_id, self.tenant)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.trust_score.value, assessment.trust_score.value)

            factors = svc.confidence_repository.list_factors(
                assessment.id, self.tenant
            )
            self.assertTrue(factors)

            versions = svc.trust_repository.list_versions(assessment.id, self.tenant)
            self.assertEqual(len(versions), 1)

            history = svc.history_repository.list_for_finding(
                self.finding_id, self.tenant
            )
            self.assertTrue(history)

    def test_rescore_increments_version(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            first = svc.scoring.score(self._input(), actor="test")
            second = svc.scoring.score(self._input(), actor="test")
            self.assertEqual(first.id, second.id)
            self.assertEqual(second.current_version, first.current_version + 1)
            versions = svc.trust_repository.list_versions(second.id, self.tenant)
            self.assertEqual(len(versions), 2)

    def test_tenant_isolation(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            assessment = svc.scoring.score(self._input(), actor="test")
            other_tenant = uuid4()
            with self.assertRaises(TrustAssessmentNotFoundError):
                svc.scoring.get_assessment(assessment.id, other_tenant)
            self.assertIsNone(
                svc.scoring.get_for_finding(self.finding_id, other_tenant)
            )

    def test_search_by_level(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            assessment = svc.scoring.score(self._input(), actor="test")
            page = svc.scoring.search(
                TrustAssessmentSearchFilter(
                    tenant_id=self.tenant,
                    trust_levels=[assessment.confidence_level],
                    min_score=0.0,
                ),
                PageRequest(page=1, page_size=10),
            )
            self.assertGreaterEqual(page.total_items, 1)
            self.assertTrue(any(i.id == assessment.id for i in page.items))


if __name__ == "__main__":
    unittest.main()
