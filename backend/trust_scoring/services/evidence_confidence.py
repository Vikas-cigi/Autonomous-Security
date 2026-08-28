"""Evidence quality / confidence assessment — deterministic, no I/O."""

from __future__ import annotations

from typing import List

from models.enums import EvidenceValidationStatus
from trust_scoring.domain.enums import (
    EvidenceQualityTier,
    FactorCategory,
    FactorPolarity,
)
from trust_scoring.domain.inputs import EvidenceItemInput
from trust_scoring.domain.models import ConfidenceFactor, EvidenceQuality
from trust_scoring.domain.weights import COMPONENT_WEIGHTS

_VALIDATION_SCORE = {
    EvidenceValidationStatus.VALIDATED: 1.0,
    EvidenceValidationStatus.PARTIALLY_VALIDATED: 0.7,
    EvidenceValidationStatus.UNVALIDATED: 0.4,
    EvidenceValidationStatus.EXPIRED: 0.25,
    EvidenceValidationStatus.REJECTED: 0.05,
    EvidenceValidationStatus.TAMPER_SUSPECTED: 0.0,
}


class EvidenceConfidenceService:
    """
    Assess evidence quality from attached EvidenceItemInput snapshots.

    Higher scores require validated, hashed, lineage-backed evidence.
    """

    ALGORITHM_VERSION = "1.0.0"

    def assess(self, items: List[EvidenceItemInput]) -> EvidenceQuality:
        if not items:
            return EvidenceQuality(
                tier=EvidenceQualityTier.INSUFFICIENT,
                score=0.15,
                evidence_count=0,
                validated_count=0,
                hashed_count=0,
                lineage_count=0,
                average_evidence_confidence=0.0,
                explanation="No evidence artifacts attached; trust is severely limited.",
            )

        validated = sum(
            1
            for i in items
            if i.validation_status
            in (
                EvidenceValidationStatus.VALIDATED,
                EvidenceValidationStatus.PARTIALLY_VALIDATED,
            )
        )
        hashed = sum(1 for i in items if i.has_content_hash)
        lineage = sum(1 for i in items if i.has_lineage)
        avg_conf = sum(i.confidence for i in items) / len(items)
        avg_validation = sum(_VALIDATION_SCORE[i.validation_status] for i in items) / len(
            items
        )

        coverage = min(1.0, len(items) / 3.0)
        hash_ratio = hashed / len(items)
        lineage_ratio = lineage / len(items)
        validated_ratio = validated / len(items)

        score = round(
            max(
                0.0,
                min(
                    1.0,
                    0.30 * avg_validation
                    + 0.25 * avg_conf
                    + 0.15 * validated_ratio
                    + 0.15 * hash_ratio
                    + 0.10 * lineage_ratio
                    + 0.05 * coverage,
                ),
            ),
            4,
        )
        tier = self._tier_for(score, len(items), validated)
        explanation = (
            f"Evidence quality {tier.value}: {len(items)} artifact(s), "
            f"{validated} validated, {hashed} hashed, {lineage} with lineage; "
            f"avg confidence={avg_conf:.2f}."
        )
        return EvidenceQuality(
            tier=tier,
            score=score,
            evidence_count=len(items),
            validated_count=validated,
            hashed_count=hashed,
            lineage_count=lineage,
            average_evidence_confidence=round(avg_conf, 4),
            explanation=explanation,
        )

    def to_factor(self, quality: EvidenceQuality) -> ConfidenceFactor:
        weight = COMPONENT_WEIGHTS[FactorCategory.EVIDENCE_QUALITY]
        polarity = (
            FactorPolarity.SUPPORTING
            if quality.score >= 0.5
            else FactorPolarity.NEGATIVE
        )
        return ConfidenceFactor(
            category=FactorCategory.EVIDENCE_QUALITY,
            polarity=polarity,
            label=f"Evidence quality: {quality.tier.value}",
            description=quality.explanation,
            raw_score=quality.score,
            weight=weight,
            weighted_contribution=round(quality.score * weight, 6),
        )

    @staticmethod
    def _tier_for(
        score: float,
        count: int,
        validated: int,
    ) -> EvidenceQualityTier:
        if count == 0:
            return EvidenceQualityTier.INSUFFICIENT
        if score >= 0.85 and validated >= 1:
            return EvidenceQualityTier.EXCELLENT
        if score >= 0.70:
            return EvidenceQualityTier.GOOD
        if score >= 0.50:
            return EvidenceQualityTier.ADEQUATE
        if score >= 0.30:
            return EvidenceQualityTier.WEAK
        return EvidenceQualityTier.INSUFFICIENT
