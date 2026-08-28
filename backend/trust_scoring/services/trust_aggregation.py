"""Trust score aggregation, weighting, time-decay, and recommendation mapping."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from trust_scoring.domain.enums import (
    FactorCategory,
    FactorPolarity,
    RecommendationConfidence,
    TrustLevel,
)
from trust_scoring.domain.inputs import (
    AssetConfidenceInput,
    FindingBaselineInput,
    IOCConfidenceInput,
    ThreatIntelConfidenceInput,
)
from trust_scoring.domain.models import ConfidenceFactor, TrustScore
from trust_scoring.domain.weights import (
    COMPONENT_WEIGHTS,
    TIME_DECAY_FLOOR,
    TIME_DECAY_HALF_LIFE_DAYS,
    trust_level_for_score,
)


class TrustAggregationService:
    """
    Aggregate component factors into a final 0–100 TrustScore.

    Aggregation is a weighted sum of component raw scores (via pre-computed
    weighted contributions), then optional exponential time-decay.
    """

    ALGORITHM_VERSION = "1.0.0"

    def asset_confidence_factor(
        self,
        asset: Optional[AssetConfidenceInput],
    ) -> Tuple[float, ConfidenceFactor]:
        weight = COMPONENT_WEIGHTS[FactorCategory.ASSET_CONFIDENCE]
        if asset is None:
            score = 0.40
            explanation = "No asset inventory signal; using reduced asset confidence."
        else:
            ownership = 1.0 if asset.ownership_known else 0.4
            environment = 1.0 if asset.environment_known else 0.5
            freshness = 1.0
            if asset.last_seen_days_ago is not None:
                freshness = max(0.4, 1.0 - asset.last_seen_days_ago / 180.0)
            crit = asset.criticality_score if asset.criticality_score is not None else 0.5
            # High criticality assets demand higher inventory confidence; low
            # inventory confidence on critical assets reduces trust.
            score = round(
                max(
                    0.0,
                    min(
                        1.0,
                        0.40 * asset.inventory_confidence
                        + 0.20 * ownership
                        + 0.15 * environment
                        + 0.15 * freshness
                        + 0.10 * (0.5 + 0.5 * crit * asset.inventory_confidence),
                    ),
                ),
                4,
            )
            explanation = (
                f"Asset confidence for {asset.asset_id}: inventory="
                f"{asset.inventory_confidence:.2f}, ownership_known="
                f"{asset.ownership_known}, environment_known={asset.environment_known}."
            )
        factor = ConfidenceFactor(
            category=FactorCategory.ASSET_CONFIDENCE,
            polarity=self._polarity(score),
            label="Asset confidence",
            description=explanation,
            raw_score=score,
            weight=weight,
            weighted_contribution=round(score * weight, 6),
        )
        return score, factor

    def threat_intel_factor(
        self,
        intel: Optional[ThreatIntelConfidenceInput],
    ) -> Tuple[float, ConfidenceFactor]:
        weight = COMPONENT_WEIGHTS[FactorCategory.THREAT_INTELLIGENCE]
        if intel is None or not intel.enrichment_present:
            score = 0.45
            explanation = "No threat intelligence enrichment; neutral TI confidence."
        else:
            base = intel.intel_confidence
            kev_boost = 0.15 if intel.in_cisa_kev else 0.0
            exploit_boost = 0.10 if intel.actively_exploited else 0.0
            cve_boost = min(0.10, intel.cve_match_count * 0.03)
            mitre_boost = min(0.08, intel.mitre_technique_count * 0.02)
            epss_boost = 0.0
            if intel.epss_score is not None:
                epss_boost = 0.10 * intel.epss_score
            score = round(
                max(
                    0.0,
                    min(
                        1.0,
                        0.55 * base
                        + kev_boost
                        + exploit_boost
                        + cve_boost
                        + mitre_boost
                        + epss_boost,
                    ),
                ),
                4,
            )
            explanation = (
                f"Threat intel confidence={score:.2f}: enrichment present, "
                f"CVE matches={intel.cve_match_count}, KEV={intel.in_cisa_kev}, "
                f"actively_exploited={intel.actively_exploited}."
            )
        factor = ConfidenceFactor(
            category=FactorCategory.THREAT_INTELLIGENCE,
            polarity=self._polarity(score),
            label="Threat intelligence confidence",
            description=explanation,
            raw_score=score,
            weight=weight,
            weighted_contribution=round(score * weight, 6),
        )
        return score, factor

    def ioc_confidence_factor(
        self,
        ioc: Optional[IOCConfidenceInput],
    ) -> Tuple[float, ConfidenceFactor]:
        weight = COMPONENT_WEIGHTS[FactorCategory.IOC_CONFIDENCE]
        if ioc is None or ioc.matched_ioc_count == 0:
            score = 0.45
            explanation = "No matched IOCs; neutral IOC confidence."
        else:
            coverage = min(1.0, ioc.matched_ioc_count / 3.0)
            active_ratio = (
                ioc.active_ioc_count / ioc.matched_ioc_count
                if ioc.matched_ioc_count
                else 0.0
            )
            score = round(
                max(
                    0.0,
                    min(
                        1.0,
                        0.50 * ioc.max_ioc_confidence
                        + 0.30 * coverage
                        + 0.20 * active_ratio,
                    ),
                ),
                4,
            )
            explanation = (
                f"IOC confidence={score:.2f}: {ioc.matched_ioc_count} match(es), "
                f"{ioc.active_ioc_count} active, max confidence="
                f"{ioc.max_ioc_confidence:.2f}."
            )
        factor = ConfidenceFactor(
            category=FactorCategory.IOC_CONFIDENCE,
            polarity=self._polarity(score),
            label="IOC confidence",
            description=explanation,
            raw_score=score,
            weight=weight,
            weighted_contribution=round(score * weight, 6),
        )
        return score, factor

    def finding_baseline_factor(
        self,
        finding: FindingBaselineInput,
    ) -> ConfidenceFactor:
        weight = COMPONENT_WEIGHTS[FactorCategory.FINDING_BASELINE]
        enrichment = 0.0
        enrichment += 0.05 if finding.has_cve else 0.0
        enrichment += 0.03 if finding.has_cwe else 0.0
        enrichment += 0.02 if finding.has_mitre else 0.0
        evidence_presence = min(0.15, finding.evidence_count * 0.05)
        score = round(
            max(0.0, min(1.0, 0.70 * finding.finding_confidence + enrichment + evidence_presence)),
            4,
        )
        return ConfidenceFactor(
            category=FactorCategory.FINDING_BASELINE,
            polarity=self._polarity(score),
            label="Finding baseline confidence",
            description=(
                f"Baseline from SecurityFindingObject confidence="
                f"{finding.finding_confidence:.2f}, evidence_count="
                f"{finding.evidence_count}."
            ),
            raw_score=score,
            weight=weight,
            weighted_contribution=round(score * weight, 6),
        )

    def compute_time_decay_multiplier(
        self,
        age_days: float,
        *,
        apply: bool = True,
    ) -> Tuple[float, Optional[ConfidenceFactor]]:
        """Exponential decay toward TIME_DECAY_FLOOR over half-life days."""

        if not apply or age_days <= 0:
            return 1.0, None

        # multiplier = floor + (1 - floor) * 0.5^(age / half_life)
        decay = math.pow(0.5, age_days / TIME_DECAY_HALF_LIFE_DAYS)
        multiplier = round(TIME_DECAY_FLOOR + (1.0 - TIME_DECAY_FLOOR) * decay, 6)
        factor = ConfidenceFactor(
            category=FactorCategory.TIME_DECAY,
            polarity=FactorPolarity.NEGATIVE if multiplier < 0.95 else FactorPolarity.NEUTRAL,
            label="Time-based confidence decay",
            description=(
                f"Finding age={age_days:.1f}d; half-life={TIME_DECAY_HALF_LIFE_DAYS}d; "
                f"decay multiplier={multiplier:.4f}."
            ),
            raw_score=multiplier,
            weight=0.0,
            weighted_contribution=0.0,
        )
        return multiplier, factor

    def aggregate(
        self,
        factors: List[ConfidenceFactor],
        *,
        time_decay_multiplier: float = 1.0,
    ) -> TrustScore:
        """
        Sum weighted contributions of weight>0 factors, apply decay, scale to 0–100.
        """

        weighted_factors = [f for f in factors if f.weight > 0]
        if not weighted_factors:
            normalized = 0.0
        else:
            # Contributions already encode weight * raw_score; sum is in [0, 1]
            # when weights sum to 1 and raw scores are in [0, 1].
            normalized = sum(f.weighted_contribution for f in weighted_factors)
            normalized = max(0.0, min(1.0, normalized))

        decayed = max(0.0, min(1.0, normalized * time_decay_multiplier))
        value = round(decayed * 100.0, 2)
        level = trust_level_for_score(value)
        return TrustScore(
            value=value,
            level=level,
            normalized_0_1=round(decayed, 6),
            time_decay_multiplier=time_decay_multiplier,
        )

    def recommendation_for(self, level: TrustLevel) -> RecommendationConfidence:
        mapping = {
            TrustLevel.VERY_HIGH: RecommendationConfidence.ACT,
            TrustLevel.HIGH: RecommendationConfidence.ACT,
            TrustLevel.MEDIUM: RecommendationConfidence.INVESTIGATE,
            TrustLevel.LOW: RecommendationConfidence.DEFER,
            TrustLevel.VERY_LOW: RecommendationConfidence.DISCARD,
        }
        return mapping[level]

    def split_factors(
        self,
        factors: List[ConfidenceFactor],
    ) -> Tuple[List[ConfidenceFactor], List[ConfidenceFactor]]:
        supporting = [f for f in factors if f.polarity == FactorPolarity.SUPPORTING]
        negative = [f for f in factors if f.polarity == FactorPolarity.NEGATIVE]
        return supporting, negative

    def build_explanation(
        self,
        trust_score: TrustScore,
        factors: List[ConfidenceFactor],
        recommendation: RecommendationConfidence,
    ) -> str:
        top_support = sorted(
            [f for f in factors if f.polarity == FactorPolarity.SUPPORTING],
            key=lambda f: f.weighted_contribution,
            reverse=True,
        )[:3]
        top_negative = sorted(
            [f for f in factors if f.polarity == FactorPolarity.NEGATIVE],
            key=lambda f: f.raw_score,
        )[:3]

        parts = [
            f"Overall trust score={trust_score.value:.2f}/100 "
            f"({trust_score.level.value}); recommendation={recommendation.value}.",
        ]
        if trust_score.time_decay_multiplier < 1.0:
            parts.append(
                f"Time decay multiplier={trust_score.time_decay_multiplier:.4f} applied."
            )
        if top_support:
            parts.append(
                "Top supporting factors: "
                + "; ".join(f"{f.label} ({f.raw_score:.2f})" for f in top_support)
                + "."
            )
        if top_negative:
            parts.append(
                "Top negative factors: "
                + "; ".join(f"{f.label} ({f.raw_score:.2f})" for f in top_negative)
                + "."
            )
        return " ".join(parts)

    @staticmethod
    def _polarity(score: float) -> FactorPolarity:
        if score >= 0.55:
            return FactorPolarity.SUPPORTING
        if score < 0.40:
            return FactorPolarity.NEGATIVE
        return FactorPolarity.NEUTRAL
