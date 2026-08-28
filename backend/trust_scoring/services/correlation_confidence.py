"""Finding correlation, duplicate, and consistency confidence — deterministic."""

from __future__ import annotations

from typing import List, Optional, Tuple

from trust_scoring.domain.enums import FactorCategory, FactorPolarity
from trust_scoring.domain.inputs import CorrelationSignalInput
from trust_scoring.domain.models import ConfidenceFactor, FindingCorrelation
from trust_scoring.domain.weights import COMPONENT_WEIGHTS


class CorrelationConfidenceService:
    """
    Analyze finding correlation, duplicates, and field consistency.

    Produces both a FindingCorrelation result and separate factors for
    correlation, duplicate-finding confidence, and consistency analysis.
    """

    ALGORITHM_VERSION = "1.0.0"

    def assess(
        self,
        signal: Optional[CorrelationSignalInput],
    ) -> FindingCorrelation:
        if signal is None:
            return FindingCorrelation(
                score=0.50,
                correlated_finding_count=0,
                duplicate_count=0,
                severity_consistency=1.0,
                type_consistency=1.0,
                asset_consistency=1.0,
                conflicting_status=False,
                explanation=(
                    "No correlation signals provided; using neutral correlation baseline."
                ),
            )

        consistency = (
            0.40 * signal.severity_consistency
            + 0.35 * signal.type_consistency
            + 0.25 * signal.asset_consistency
        )
        # Independent corroboration via correlated findings boosts trust.
        corr_boost = min(0.25, signal.correlated_finding_count * 0.05)
        # Exact duplicates modestly boost (same issue re-observed).
        dup_boost = min(0.15, signal.duplicate_count * 0.03)
        conflict_penalty = 0.25 if signal.conflicting_status else 0.0

        score = round(
            max(0.0, min(1.0, consistency + corr_boost + dup_boost - conflict_penalty)),
            4,
        )
        return FindingCorrelation(
            score=score,
            correlated_finding_count=signal.correlated_finding_count,
            duplicate_count=signal.duplicate_count,
            severity_consistency=signal.severity_consistency,
            type_consistency=signal.type_consistency,
            asset_consistency=signal.asset_consistency,
            conflicting_status=signal.conflicting_status,
            explanation=(
                f"Correlation score={score:.2f}: "
                f"{signal.correlated_finding_count} correlated, "
                f"{signal.duplicate_count} duplicate(s); "
                f"consistency(sev/type/asset)="
                f"{signal.severity_consistency:.2f}/"
                f"{signal.type_consistency:.2f}/"
                f"{signal.asset_consistency:.2f}"
                f"{'; conflicting status' if signal.conflicting_status else ''}."
            ),
        )

    def to_factors(
        self,
        correlation: FindingCorrelation,
    ) -> Tuple[ConfidenceFactor, List[ConfidenceFactor]]:
        """Return primary correlation factor plus duplicate/consistency factors."""

        primary_weight = COMPONENT_WEIGHTS[FactorCategory.FINDING_CORRELATION]
        primary = ConfidenceFactor(
            category=FactorCategory.FINDING_CORRELATION,
            polarity=self._polarity(correlation.score),
            label="Finding correlation",
            description=correlation.explanation,
            raw_score=correlation.score,
            weight=primary_weight,
            weighted_contribution=round(correlation.score * primary_weight, 6),
        )

        extras: List[ConfidenceFactor] = []

        dup_score = min(1.0, 0.45 + correlation.duplicate_count * 0.08)
        if correlation.duplicate_count == 0:
            dup_score = 0.45
        dup_weight = COMPONENT_WEIGHTS[FactorCategory.DUPLICATE_FINDING]
        extras.append(
            ConfidenceFactor(
                category=FactorCategory.DUPLICATE_FINDING,
                polarity=self._polarity(dup_score),
                label="Duplicate finding confidence",
                description=(
                    f"{correlation.duplicate_count} duplicate observation(s) "
                    f"of the same finding signature."
                ),
                raw_score=round(dup_score, 4),
                weight=dup_weight,
                weighted_contribution=round(dup_score * dup_weight, 6),
            )
        )

        consistency_score = round(
            (
                0.40 * correlation.severity_consistency
                + 0.35 * correlation.type_consistency
                + 0.25 * correlation.asset_consistency
            ),
            4,
        )
        if correlation.conflicting_status:
            consistency_score = round(max(0.0, consistency_score - 0.3), 4)
        cons_weight = COMPONENT_WEIGHTS[FactorCategory.CONSISTENCY]
        extras.append(
            ConfidenceFactor(
                category=FactorCategory.CONSISTENCY,
                polarity=self._polarity(consistency_score),
                label="Finding consistency analysis",
                description=(
                    "Severity/type/asset field consistency across correlated findings."
                ),
                raw_score=consistency_score,
                weight=cons_weight,
                weighted_contribution=round(consistency_score * cons_weight, 6),
            )
        )
        return primary, extras

    @staticmethod
    def _polarity(score: float) -> FactorPolarity:
        if score >= 0.55:
            return FactorPolarity.SUPPORTING
        if score < 0.40:
            return FactorPolarity.NEGATIVE
        return FactorPolarity.NEUTRAL
