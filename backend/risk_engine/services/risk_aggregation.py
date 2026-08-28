"""RiskAggregationService — combine pillars into EnterpriseRiskScore."""

from __future__ import annotations

from typing import List, Optional, Tuple

from risk_engine.domain.enums import FactorCategory, FactorPolarity
from risk_engine.domain.inputs import HistoricalRiskInput, TrustRiskInput
from risk_engine.domain.models import (
    EnterpriseRiskScore,
    RiskExplanation,
    RiskFactor,
)
from risk_engine.domain.weights import (
    HISTORICAL_BLEND_WEIGHT,
    PILLAR_WEIGHTS,
    priority_for_level,
    risk_level_for_score,
    sla_for_level,
)


class RiskAggregationService:
    """
    Aggregate pillar scores into a final 0-100 EnterpriseRiskScore.

    Aggregation is a weighted sum of pillar contributions, with optional
    historical blend. Trust is a first-class pillar: low trust dampens risk.
    """

    def trust_factor(self, trust: TrustRiskInput) -> Tuple[float, RiskFactor]:
        normalized = round(max(0.0, min(1.0, trust.trust_score / 100.0)), 4)
        weight = PILLAR_WEIGHTS["trust"]
        explanation = (
            f"Trust pillar={normalized:.2f} from Trust Score "
            f"{trust.trust_score:.2f}/100"
            + (
                f" ({trust.trust_level})"
                if trust.trust_level
                else ""
            )
            + "."
        )
        # Low trust mitigates actionable risk; high trust elevates it.
        if normalized >= 0.55:
            polarity = FactorPolarity.ELEVATING
        elif normalized < 0.40:
            polarity = FactorPolarity.MITIGATING
        else:
            polarity = FactorPolarity.NEUTRAL
        factor = RiskFactor(
            category=FactorCategory.TRUST,
            polarity=polarity,
            label="Trust score pillar",
            description=explanation,
            raw_score=normalized,
            weight=weight,
            weighted_contribution=round(normalized * weight, 6),
        )
        return normalized, factor

    def historical_factor(
        self,
        historical: Optional[HistoricalRiskInput],
        *,
        apply: bool,
    ) -> Optional[RiskFactor]:
        if (
            not apply
            or historical is None
            or historical.prior_risk_score is None
        ):
            return None
        prior_norm = round(historical.prior_risk_score / 100.0, 4)
        return RiskFactor(
            category=FactorCategory.HISTORICAL,
            polarity=FactorPolarity.NEUTRAL,
            label="Historical risk blend",
            description=(
                f"Prior enterprise risk={historical.prior_risk_score:.2f}/100 "
                f"(blend weight={HISTORICAL_BLEND_WEIGHT:.2f})."
            ),
            raw_score=prior_norm,
            weight=0.0,
            weighted_contribution=0.0,
        )

    def aggregate(
        self,
        factors: List[RiskFactor],
        *,
        historical: Optional[HistoricalRiskInput] = None,
        apply_historical_blend: bool = True,
    ) -> EnterpriseRiskScore:
        weighted = [f for f in factors if f.weight > 0]
        if not weighted:
            normalized = 0.0
        else:
            normalized = sum(f.weighted_contribution for f in weighted)
            normalized = max(0.0, min(1.0, normalized))

        blended = False
        if (
            apply_historical_blend
            and historical is not None
            and historical.prior_risk_score is not None
        ):
            prior = historical.prior_risk_score / 100.0
            w = HISTORICAL_BLEND_WEIGHT
            normalized = max(0.0, min(1.0, (1.0 - w) * normalized + w * prior))
            blended = True

        value = round(normalized * 100.0, 2)
        level = risk_level_for_score(value)
        return EnterpriseRiskScore(
            value=value,
            level=level,
            normalized_0_1=round(normalized, 6),
            historical_blend_applied=blended,
        )

    def build_explanation(
        self,
        risk_score: EnterpriseRiskScore,
        factors: List[RiskFactor],
    ) -> RiskExplanation:
        elevating = sorted(
            [f for f in factors if f.polarity == FactorPolarity.ELEVATING],
            key=lambda f: (f.weighted_contribution, f.raw_score),
            reverse=True,
        )[:5]
        mitigating = sorted(
            [f for f in factors if f.polarity == FactorPolarity.MITIGATING],
            key=lambda f: f.raw_score,
        )[:5]

        sla = sla_for_level(risk_score.level)
        priority = priority_for_level(risk_score.level)
        summary = (
            f"Enterprise risk score={risk_score.value:.2f}/100 "
            f"({risk_score.level.value}); priority={priority.value}; "
            f"recommended SLA={sla.value}."
        )
        top_e = [f"{f.label} ({f.raw_score:.2f})" for f in elevating]
        top_m = [f"{f.label} ({f.raw_score:.2f})" for f in mitigating]
        rationale_parts = [summary]
        if risk_score.historical_blend_applied:
            rationale_parts.append(
                f"Historical blend weight={HISTORICAL_BLEND_WEIGHT:.2f} applied."
            )
        if top_e:
            rationale_parts.append("Top elevating factors: " + "; ".join(top_e) + ".")
        if top_m:
            rationale_parts.append("Top mitigating factors: " + "; ".join(top_m) + ".")
        return RiskExplanation(
            summary=summary,
            top_elevating_factors=top_e,
            top_mitigating_factors=top_m,
            rationale=" ".join(rationale_parts),
        )
