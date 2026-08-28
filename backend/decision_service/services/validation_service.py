"""DecisionValidationService — request validation and policy gate."""

from __future__ import annotations

from typing import Optional, Tuple

from models.common import ActorReference
from models.enums import ActionClass, DecisionAction, PolicyScope, PolicyVerdict, Priority
from policy_engine.engine import PolicyEngine
from policy_engine.models import PolicyDecision, PolicyInput, ResourceRef

from decision_service.domain.enums import SecurityDecisionType
from decision_service.domain.inputs import DecisionRequest
from decision_service.domain.mapping import to_decision_action, to_recommended_action
from decision_service.domain.models import DecisionRecommendation
from decision_service.exceptions import InvalidDecisionRequestError


class DecisionValidationService:
    """
    Validate DecisionRequest integrity and evaluate Policy Engine gates.

    Does not implement policy rules — delegates to injected PolicyEngine when
    present, or honors precomputed verdicts on the request.
    """

    def __init__(self, policy_engine: Optional[PolicyEngine] = None) -> None:
        self._policy_engine = policy_engine

    def validate_request(self, request: DecisionRequest) -> None:
        finding = request.finding
        if request.asset is not None and request.asset.asset_id != finding.asset_id:
            raise InvalidDecisionRequestError(
                "asset.asset_id must match finding.asset_id",
                details={
                    "finding_asset_id": str(finding.asset_id),
                    "asset_id": str(request.asset.asset_id),
                },
            )
        if request.trust.trust_score < 0 or request.risk.enterprise_risk_score < 0:
            raise InvalidDecisionRequestError("scores must be non-negative")

    def ensure_approval_rules(
        self,
        recommendation: DecisionRecommendation,
        *,
        owner: ActorReference,
        approver: Optional[ActorReference],
    ) -> Tuple[DecisionRecommendation, Optional[ActorReference]]:
        """
        Align high-impact remediations with DecisionObject approval rules.

        If REMEDIATE at P0/P1 lacks an approver, downgrade to ESCALATE so the
        canonical DecisionObject validators remain satisfied.
        """

        action = to_decision_action(recommendation.decision_type)
        high_impact = action == DecisionAction.REMEDIATE
        high_priority = recommendation.priority in {Priority.P0, Priority.P1}

        if high_impact and high_priority and approver is None:
            # Fail closed to escalate rather than emit an invalid DecisionObject.
            downgraded = recommendation.model_copy(
                update={
                    "decision_type": SecurityDecisionType.ESCALATE,
                    "recommended_action": to_recommended_action(
                        SecurityDecisionType.ESCALATE
                    ),
                    "next_step": (
                        "Escalate for dual-control approval before remediation "
                        f"(priority={recommendation.priority.value})."
                    ),
                    "business_justification": (
                        recommendation.business_justification
                        + " Downgraded to escalate: P0/P1 remediate requires approver."
                    )[:4000],
                }
            )
            return downgraded, None

        if (
            high_impact
            and high_priority
            and approver is not None
            and approver.actor_id == owner.actor_id
        ):
            raise InvalidDecisionRequestError(
                "approver must be distinct from owner for P0/P1 remediate decisions"
            )
        return recommendation, approver

    def evaluate_policy(
        self,
        request: DecisionRequest,
        recommendation: DecisionRecommendation,
    ) -> PolicyDecision:
        """Return a PolicyDecision for the recommended action."""

        action_class = self._action_class_for(recommendation.decision_type)
        resource_id = request.finding.finding_id

        if request.policy.precomputed_verdict:
            verdict_token = request.policy.precomputed_verdict.strip().lower()
            try:
                verdict = PolicyVerdict(verdict_token)
            except ValueError:
                verdict = PolicyVerdict.DENY
            return PolicyDecision(
                tenant_id=request.finding.tenant_id,
                verdict=verdict,
                reason=request.policy.precomputed_reason
                or f"Precomputed policy verdict={verdict.value}",
                action_class=action_class,
                resource_id=resource_id,
                matched_rule_ids=list(request.policy.related_policy_ids),
                requires_approval=(verdict == PolicyVerdict.ESCALATE),
                evaluator="precomputed",
                policy_version=request.policy.policy_version,
            )

        if self._policy_engine is None:
            # Fail-open for SUGGEST-class decision proposals when no engine wired.
            return PolicyDecision(
                tenant_id=request.finding.tenant_id,
                verdict=PolicyVerdict.ALLOW,
                reason="No PolicyEngine configured; allowing decision proposal.",
                action_class=action_class,
                resource_id=resource_id,
                matched_rule_ids=[],
                evaluator="decision_service.passthrough",
                policy_version=request.policy.policy_version,
            )

        policy_input = PolicyInput(
            tenant_id=request.finding.tenant_id,
            user=request.owner,
            scope=request.policy.scope or PolicyScope.TENANT,
            action_class=action_class,
            resource=ResourceRef(
                resource_type="finding",
                resource_id=resource_id,
                environment=request.asset.environment if request.asset else None,
            ),
            roles=list(request.policy.roles),
            attributes={
                **dict(request.policy.attributes),
                "decision_type": recommendation.decision_type.value,
                "risk_score": request.risk.enterprise_risk_score,
                "trust_score": request.trust.trust_score,
            },
        )
        return self._policy_engine.evaluate(policy_input)

    @staticmethod
    def _action_class_for(decision_type: SecurityDecisionType) -> ActionClass:
        if decision_type == SecurityDecisionType.REMEDIATE:
            return ActionClass.PLAN
        if decision_type == SecurityDecisionType.ESCALATE:
            return ActionClass.SUGGEST
        return ActionClass.SUGGEST
