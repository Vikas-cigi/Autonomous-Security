"""DecisionExplanationService — assemble operator-facing explanations."""

from __future__ import annotations

from decision_service.domain.models import (
    DecisionContext,
    DecisionExplanation,
    DecisionRecommendation,
)


class DecisionExplanationService:
    """Build DecisionExplanation from context + recommendation (+ optional AI text)."""

    def explain(
        self,
        context: DecisionContext,
        recommendation: DecisionRecommendation,
        *,
        ai_explanation: str | None = None,
    ) -> DecisionExplanation:
        supporting = list(context.reasoning.key_signals)
        for eid in context.evidence_ids[:12]:
            supporting.append(f"evidence_id={eid}")

        summary = (
            f"Decision={recommendation.decision_type.value} "
            f"(confidence={recommendation.confidence:.2f}, "
            f"priority={recommendation.priority.value}, "
            f"source={recommendation.source.value}). "
            f"Risk={context.enterprise_risk_score:.2f}/100 "
            f"({context.risk_level or 'n/a'}); "
            f"Trust={context.trust_score:.2f}/100 "
            f"({context.trust_level or 'n/a'})."
        )

        return DecisionExplanation(
            summary=summary,
            ai_explanation=ai_explanation or recommendation.raw_ai_text,
            business_justification=recommendation.business_justification,
            technical_justification=recommendation.technical_justification,
            risk_summary=context.reasoning.risk_summary,
            supporting_evidence=supporting,
            recommended_next_step=recommendation.next_step,
        )
