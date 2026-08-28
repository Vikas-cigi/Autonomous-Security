"""ComplianceRiskService — compliance framework impact."""

from __future__ import annotations

from typing import List, Optional, Tuple

from risk_engine.domain.enums import FactorCategory, FactorPolarity
from risk_engine.domain.inputs import AssetRiskInput
from risk_engine.domain.models import ComplianceImpact, RiskFactor
from risk_engine.domain.weights import COMPLIANCE_FRAMEWORK_WEIGHTS, PILLAR_WEIGHTS


class ComplianceRiskService:
    """Deterministic compliance impact scoring."""

    def assess(
        self,
        asset: Optional[AssetRiskInput],
    ) -> Tuple[ComplianceImpact, List[RiskFactor]]:
        if asset is None or not asset.compliance_tags:
            impact = ComplianceImpact(
                score=0.15,
                frameworks=[],
                highest_framework_weight=0.0,
                explanation="No compliance tags; low compliance impact.",
            )
        else:
            weights = [
                COMPLIANCE_FRAMEWORK_WEIGHTS.get(tag, 0.5)
                for tag in asset.compliance_tags
            ]
            highest = max(weights) if weights else 0.0
            # Multiple frameworks increase pressure slightly.
            coverage = min(1.0, 0.70 * highest + 0.30 * min(1.0, len(weights) / 3.0))
            score = round(coverage, 4)
            frameworks = [tag.value for tag in asset.compliance_tags]
            impact = ComplianceImpact(
                score=score,
                frameworks=frameworks,
                highest_framework_weight=highest,
                explanation=(
                    f"Compliance impact={score:.2f}: frameworks={frameworks}, "
                    f"highest_weight={highest:.2f}."
                ),
            )

        weight = PILLAR_WEIGHTS["compliance"]
        factors = [
            RiskFactor(
                category=FactorCategory.COMPLIANCE,
                polarity=self._polarity(impact.score),
                label="Compliance impact",
                description=impact.explanation,
                raw_score=impact.score,
                weight=weight,
                weighted_contribution=round(impact.score * weight, 6),
            )
        ]
        return impact, factors

    @staticmethod
    def _polarity(score: float) -> FactorPolarity:
        if score >= 0.55:
            return FactorPolarity.ELEVATING
        if score < 0.25:
            return FactorPolarity.MITIGATING
        return FactorPolarity.NEUTRAL
