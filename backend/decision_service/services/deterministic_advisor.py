"""Deterministic advisor — rule-based recommendation without AI."""

from __future__ import annotations

from models.enums import RecommendedAction
from decision_service.domain.enums import DecisionSource, SecurityDecisionType
from decision_service.domain.mapping import (
    to_canonical_priority,
    to_recommended_action,
)
from decision_service.domain.models import DecisionContext, DecisionRecommendation


class DeterministicDecisionAdvisor:
    """
    Produce a SecurityDecisionType recommendation from Trust + Risk signals.

    Used when invoke_ai=False or when AI parsing fails. Contains orchestration
    rules only — does not recompute trust/risk scores.
    """

    def recommend(
        self,
        context: DecisionContext,
        *,
        preferred_action: RecommendedAction | None = None,
    ) -> DecisionRecommendation:
        decision_type = self._select_type(context)
        priority = to_canonical_priority(context.risk_priority, context.risk_level)
        confidence = self._confidence(context, decision_type)
        recommended = to_recommended_action(
            decision_type,
            override=preferred_action,
        )

        business = (
            f"Business-facing risk level={context.risk_level or 'unknown'} "
            f"(score={context.enterprise_risk_score:.2f}). "
            f"Customer-facing={context.customer_facing}; "
            f"compliance={context.compliance_tags or ['none']}."
        )
        technical = (
            f"Trust={context.trust_score:.2f}/100; "
            f"KEV={context.in_cisa_kev}; exploited={context.actively_exploited}; "
            f"internet_facing={context.internet_facing}; "
            f"evidence_count={context.evidence_count}."
        )
        next_step = self._next_step(decision_type, context)

        return DecisionRecommendation(
            decision_type=decision_type,
            confidence=confidence,
            recommended_action=recommended,
            priority=priority,
            next_step=next_step,
            business_justification=business,
            technical_justification=technical,
            source=DecisionSource.DETERMINISTIC,
        )

    def _select_type(self, context: DecisionContext) -> SecurityDecisionType:
        risk = context.enterprise_risk_score
        trust = context.trust_score
        level = (context.risk_level or "").lower()

        # Low trust → investigate rather than act.
        if trust < 40.0:
            return SecurityDecisionType.INVESTIGATE

        if context.in_cisa_kev or context.actively_exploited:
            if trust >= 50.0 and risk >= 40.0:
                return SecurityDecisionType.REMEDIATE
            return SecurityDecisionType.ESCALATE

        if level == "critical" or risk >= 90.0:
            return (
                SecurityDecisionType.REMEDIATE
                if trust >= 60.0
                else SecurityDecisionType.ESCALATE
            )

        if level == "high" or risk >= 70.0:
            if trust >= 55.0:
                return SecurityDecisionType.REMEDIATE
            return SecurityDecisionType.INVESTIGATE

        if level == "medium" or risk >= 40.0:
            if context.internet_facing or context.customer_facing:
                return SecurityDecisionType.INVESTIGATE
            return SecurityDecisionType.MONITOR

        if trust < 50.0 or risk < 20.0:
            return SecurityDecisionType.IGNORE

        return SecurityDecisionType.MONITOR

    @staticmethod
    def _confidence(
        context: DecisionContext,
        decision_type: SecurityDecisionType,
    ) -> float:
        # Blend normalized trust and risk agreement into decision confidence.
        trust_n = context.trust_score / 100.0
        risk_n = context.enterprise_risk_score / 100.0
        base = 0.55 * trust_n + 0.45 * risk_n
        if decision_type == SecurityDecisionType.INVESTIGATE and trust_n < 0.5:
            base = min(base, 0.55)
        if decision_type == SecurityDecisionType.REMEDIATE and (
            context.in_cisa_kev or context.actively_exploited
        ):
            base = max(base, 0.70)
        return round(max(0.05, min(0.99, base)), 4)

    @staticmethod
    def _next_step(
        decision_type: SecurityDecisionType,
        context: DecisionContext,
    ) -> str:
        mapping = {
            SecurityDecisionType.REMEDIATE: (
                "Draft remediation plan and route to Remediation Planner "
                f"(SLA={context.recommended_sla or 'per policy'})."
            ),
            SecurityDecisionType.IGNORE: (
                "Close as no-action after verification; retain audit trail."
            ),
            SecurityDecisionType.ESCALATE: (
                "Escalate to human approver / higher privilege queue before action."
            ),
            SecurityDecisionType.INVESTIGATE: (
                "Collect additional evidence / corroboration before remediation."
            ),
            SecurityDecisionType.MONITOR: (
                "Continue monitoring; reassess when trust or risk signals change."
            ),
        }
        return mapping[decision_type]
