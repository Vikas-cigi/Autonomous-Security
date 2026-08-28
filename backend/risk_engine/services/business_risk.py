"""BusinessRiskService — asset/business criticality and environment context."""

from __future__ import annotations

from typing import List, Optional, Tuple

from risk_engine.domain.enums import BusinessContext, FactorCategory, FactorPolarity
from risk_engine.domain.inputs import AssetRiskInput
from risk_engine.domain.models import BusinessImpact, RiskFactor
from risk_engine.domain.weights import (
    BUSINESS_SUB_WEIGHTS,
    ENVIRONMENT_SCORES,
    PILLAR_WEIGHTS,
)


class BusinessRiskService:
    """Deterministic business impact scoring."""

    def assess(
        self,
        asset: Optional[AssetRiskInput],
    ) -> Tuple[BusinessImpact, List[RiskFactor]]:
        if asset is None:
            score = 0.40
            impact = BusinessImpact(
                score=score,
                asset_criticality=0.5,
                business_criticality=0.5,
                environment_score=0.4,
                customer_facing=False,
                explanation="No asset inventory signal; using neutral business impact.",
            )
        else:
            env_score = self._environment_score(asset)
            customer = 1.0 if asset.customer_facing else 0.0
            score = round(
                max(
                    0.0,
                    min(
                        1.0,
                        BUSINESS_SUB_WEIGHTS["asset_criticality"] * asset.asset_criticality
                        + BUSINESS_SUB_WEIGHTS["business_criticality"]
                        * asset.business_criticality
                        + BUSINESS_SUB_WEIGHTS["environment"] * env_score
                        + BUSINESS_SUB_WEIGHTS["customer_facing"] * customer,
                    ),
                ),
                4,
            )
            impact = BusinessImpact(
                score=score,
                asset_criticality=asset.asset_criticality,
                business_criticality=asset.business_criticality,
                environment_score=env_score,
                customer_facing=asset.customer_facing,
                explanation=(
                    f"Business impact={score:.2f}: asset_crit={asset.asset_criticality:.2f}, "
                    f"business_crit={asset.business_criticality:.2f}, "
                    f"environment={env_score:.2f}, customer_facing={asset.customer_facing}."
                ),
            )

        weight = PILLAR_WEIGHTS["business"]
        factors = [
            RiskFactor(
                category=FactorCategory.BUSINESS,
                polarity=self._polarity(impact.score),
                label="Business impact",
                description=impact.explanation,
                raw_score=impact.score,
                weight=weight,
                weighted_contribution=round(impact.score * weight, 6),
            )
        ]
        if asset is not None and asset.asset_criticality >= 0.8:
            factors.append(
                RiskFactor(
                    category=FactorCategory.ASSET_CRITICALITY,
                    polarity=FactorPolarity.ELEVATING,
                    label="High asset criticality",
                    description=(
                        f"Asset criticality={asset.asset_criticality:.2f} elevates enterprise risk."
                    ),
                    raw_score=asset.asset_criticality,
                    weight=0.0,
                    weighted_contribution=0.0,
                )
            )
        return impact, factors

    @staticmethod
    def _environment_score(asset: AssetRiskInput) -> float:
        if not asset.environments:
            # Fallback from boolean flags when enum list empty.
            if asset.internet_facing:
                return ENVIRONMENT_SCORES[BusinessContext.INTERNET_FACING]
            return ENVIRONMENT_SCORES[BusinessContext.INTERNAL]
        return max(ENVIRONMENT_SCORES.get(env, 0.4) for env in asset.environments)

    @staticmethod
    def _polarity(score: float) -> FactorPolarity:
        if score >= 0.55:
            return FactorPolarity.ELEVATING
        if score < 0.30:
            return FactorPolarity.MITIGATING
        return FactorPolarity.NEUTRAL
