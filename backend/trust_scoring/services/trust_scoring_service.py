"""TrustScoringService — facade orchestrating deterministic trust assessment."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from models.common import utc_now
from trust_scoring.domain.enums import AuditAction
from trust_scoring.domain.inputs import TrustScoringInput
from trust_scoring.domain.models import TrustAssessment
from trust_scoring.exceptions import InvalidScoringInputError
from trust_scoring.interfaces.confidence_repository import ConfidenceRepository
from trust_scoring.interfaces.trust_history_repository import TrustHistoryRepository
from trust_scoring.interfaces.trust_repository import TrustRepository
from trust_scoring.query.filters import TrustAssessmentSearchFilter
from trust_scoring.query.pagination import Page, PageRequest
from trust_scoring.services.audit import AuditLogger
from trust_scoring.services.correlation_confidence import CorrelationConfidenceService
from trust_scoring.services.cross_validation import CrossValidationService
from trust_scoring.services.evidence_confidence import EvidenceConfidenceService
from trust_scoring.services.historical_trust import HistoricalTrustService
from trust_scoring.services.trust_aggregation import TrustAggregationService


ALGORITHM_VERSION = "1.0.0"


class TrustScoringService:
    """
    Evaluate and persist TrustAssessment for a SecurityFindingObject.

    Deterministic: identical TrustScoringInput always yields the same score
    components (UUIDs on factors/assessments may differ unless provided).
    No AI, LLM, or external API calls.
    """

    def __init__(
        self,
        trust_repository: TrustRepository,
        *,
        confidence_repository: Optional[ConfidenceRepository] = None,
        history_repository: Optional[TrustHistoryRepository] = None,
        evidence_service: Optional[EvidenceConfidenceService] = None,
        cross_validation_service: Optional[CrossValidationService] = None,
        historical_service: Optional[HistoricalTrustService] = None,
        correlation_service: Optional[CorrelationConfidenceService] = None,
        aggregation_service: Optional[TrustAggregationService] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._trust_repo = trust_repository
        self._confidence_repo = confidence_repository
        self._history_repo = history_repository
        self._evidence = evidence_service or EvidenceConfidenceService()
        self._cross = cross_validation_service or CrossValidationService()
        self._historical = historical_service or HistoricalTrustService()
        self._correlation = correlation_service or CorrelationConfidenceService()
        self._aggregation = aggregation_service or TrustAggregationService()
        self._audit = audit_logger

    def score(
        self,
        scoring_input: TrustScoringInput,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        assessment_id: Optional[UUID] = None,
    ) -> TrustAssessment:
        """Compute (and optionally persist) a TrustAssessment."""

        self._validate_input(scoring_input)
        assessment = self.compute(scoring_input, assessment_id=assessment_id)

        if persist:
            assessment = self._trust_repo.save_assessment(
                assessment,
                actor=actor,
                change_summary="Trust score computed",
            )
            all_factors = assessment.supporting_factors + assessment.negative_factors
            # Include neutrals stored only in explanation path — recompute full list.
            # Persist factors that were attached on supporting/negative; also any
            # neutrals are omitted from those lists by design.
            if self._confidence_repo is not None:
                # Re-score factors for persistence including neutrals via compute internals
                # is unnecessary; persist supporting + negative which drive decisions.
                self._confidence_repo.replace_factors(
                    assessment_id=assessment.id,
                    tenant_id=assessment.tenant_id,
                    finding_id=assessment.finding_id,
                    factors=all_factors,
                    actor=actor,
                )
            if self._audit is not None:
                self._audit.log(
                    tenant_id=assessment.tenant_id,
                    action=AuditAction.ASSESSMENT_SCORED,
                    message=(
                        f"Scored finding {assessment.finding_id} "
                        f"at {assessment.trust_score.value}"
                    ),
                    actor=actor,
                    details={
                        "assessment_id": str(assessment.id),
                        "score": assessment.trust_score.value,
                        "level": assessment.confidence_level.value,
                        "algorithm_version": assessment.algorithm_version,
                    },
                )
        return assessment

    def compute(
        self,
        scoring_input: TrustScoringInput,
        *,
        assessment_id: Optional[UUID] = None,
    ) -> TrustAssessment:
        """Pure computation — no persistence. Fully deterministic given inputs."""

        finding = scoring_input.finding
        factors = []

        # Evidence quality
        evidence_quality = self._evidence.assess(scoring_input.evidence_items)
        factors.append(self._evidence.to_factor(evidence_quality))

        # Scanner + cross-validation
        scanner = self._cross.assess_scanner_confidence(
            scoring_input.scanner_observations,
            primary_tool=finding.source_tool,
        )
        factors.append(self._cross.scanner_factor(scanner))
        cross_val = self._cross.cross_validate(scoring_input.scanner_observations)
        factors.append(self._cross.cross_validation_factor(cross_val))

        # Historical reliability
        historical = self._historical.assess(scoring_input.historical)
        factors.append(self._historical.to_factor(historical))

        # Correlation / duplicates / consistency
        correlation = self._correlation.assess(scoring_input.correlation)
        primary_corr, extra_corr = self._correlation.to_factors(correlation)
        factors.append(primary_corr)
        factors.extend(extra_corr)

        # Asset / TI / IOC / baseline
        asset_score, asset_factor = self._aggregation.asset_confidence_factor(
            scoring_input.asset
        )
        factors.append(asset_factor)

        ti_score, ti_factor = self._aggregation.threat_intel_factor(
            scoring_input.threat_intel
        )
        factors.append(ti_factor)

        ioc_score, ioc_factor = self._aggregation.ioc_confidence_factor(scoring_input.ioc)
        factors.append(ioc_factor)

        factors.append(self._aggregation.finding_baseline_factor(finding))

        # Time decay (multiplicative)
        decay_mult, decay_factor = self._aggregation.compute_time_decay_multiplier(
            finding.finding_age_days,
            apply=scoring_input.apply_time_decay,
        )
        if decay_factor is not None:
            factors.append(decay_factor)

        trust_score = self._aggregation.aggregate(
            factors,
            time_decay_multiplier=decay_mult,
        )
        recommendation = self._aggregation.recommendation_for(trust_score.level)
        supporting, negative = self._aggregation.split_factors(factors)
        explanation = self._aggregation.build_explanation(
            trust_score, factors, recommendation
        )

        now = finding.evaluated_at or utc_now()
        kwargs = {
            "tenant_id": finding.tenant_id,
            "finding_id": finding.finding_id,
            "asset_id": finding.asset_id,
            "trust_score": trust_score,
            "confidence_level": trust_score.level,
            "recommendation_confidence": recommendation,
            "supporting_factors": supporting,
            "negative_factors": negative,
            "evidence_quality": evidence_quality,
            "scanner_confidence": scanner,
            "cross_validation": cross_val,
            "historical_reliability": historical,
            "finding_correlation": correlation,
            "asset_confidence_score": asset_score,
            "threat_intel_confidence_score": ti_score,
            "ioc_confidence_score": ioc_score,
            "confidence_explanation": explanation,
            "scored_at": now,
            "algorithm_version": ALGORITHM_VERSION,
            "first_scored_at": now,
            "last_scored_at": now,
        }
        if assessment_id is not None:
            kwargs["id"] = assessment_id
        return TrustAssessment(**kwargs)

    def get_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[TrustAssessment]:
        return self._trust_repo.find_by_finding(finding_id, tenant_id)

    def get_assessment(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> TrustAssessment:
        return self._trust_repo.get_assessment(assessment_id, tenant_id)

    def search(
        self,
        filters: TrustAssessmentSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[TrustAssessment]:
        return self._trust_repo.search_assessments(
            filters,
            page or PageRequest(),
        )

    @staticmethod
    def _validate_input(scoring_input: TrustScoringInput) -> None:
        finding = scoring_input.finding
        if scoring_input.asset is not None and scoring_input.asset.asset_id != finding.asset_id:
            raise InvalidScoringInputError(
                "asset.asset_id must match finding.asset_id",
                details={
                    "finding_asset_id": str(finding.asset_id),
                    "asset_id": str(scoring_input.asset.asset_id),
                },
            )
