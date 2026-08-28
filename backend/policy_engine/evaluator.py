"""
PolicyEvaluator — pure rule matching and decision construction.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from models.enums import ActionClass, PolicyVerdict, Severity
from policy_engine.models import PolicyDecision, PolicyInput, PolicyRuleSpec

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {
    Severity.UNKNOWN: 0,
    Severity.INFORMATIONAL: 1,
    Severity.LOW: 2,
    Severity.MEDIUM: 3,
    Severity.HIGH: 4,
    Severity.CRITICAL: 5,
}


class PolicyEvaluator:
    """
    Deterministic evaluator over ``PolicyRuleSpec`` documents.

    Contains matching business logic only — no I/O, UI, or AI.
    """

    def __init__(self, backend_name: str = "local") -> None:
        self._backend_name = backend_name

    def evaluate(
        self,
        policy_input: PolicyInput,
        rules: Sequence[PolicyRuleSpec],
    ) -> PolicyDecision:
        """
        First-match evaluation ordered by ascending priority.

        If no rule matches, returns DENY (fail closed / never execute without policy).
        """

        ordered = sorted(
            (rule for rule in rules if rule.enabled),
            key=lambda rule: (rule.priority, rule.name),
        )

        for rule in ordered:
            if self.matches(policy_input, rule):
                decision = self._to_decision(policy_input, rule)
                logger.info(
                    "Policy rule matched name=%s verdict=%s action=%s",
                    rule.name,
                    decision.verdict.value,
                    policy_input.action_class.value,
                )
                return decision

        logger.warning(
            "No policy matched; denying action_class=%s tenant_id=%s resource_id=%s",
            policy_input.action_class.value,
            policy_input.tenant_id,
            policy_input.resource.resource_id,
        )
        return self.deny_without_policy(policy_input)

    def matches(self, policy_input: PolicyInput, rule: PolicyRuleSpec) -> bool:
        """Return True when all rule predicates match the input."""

        if policy_input.action_class not in rule.action_classes:
            return False

        if policy_input.scope not in rule.scopes:
            return False

        if rule.environments:
            env = (policy_input.resource.environment or "").lower()
            if env not in rule.environments:
                return False

        if rule.resource_types:
            if policy_input.resource.resource_type not in rule.resource_types:
                return False

        if rule.required_roles:
            caller_roles = set(policy_input.roles)
            if caller_roles.isdisjoint(set(rule.required_roles)):
                return False

        if rule.min_severity is not None or rule.max_severity is not None:
            if policy_input.finding is None:
                return False
            rank = _SEVERITY_RANK[policy_input.finding.severity]
            if rule.min_severity is not None and rank < _SEVERITY_RANK[rule.min_severity]:
                return False
            if rule.max_severity is not None and rank > _SEVERITY_RANK[rule.max_severity]:
                return False

        return True

    def deny_without_policy(self, policy_input: PolicyInput) -> PolicyDecision:
        """Fail-closed decision when no rule authorizes the action."""

        return PolicyDecision(
            verdict=PolicyVerdict.DENY,
            reason=(
                "Denied: no matching policy rule for "
                f"{policy_input.action_class.value} "
                "(never execute without policy)."
            ),
            action_class=policy_input.action_class,
            tenant_id=policy_input.tenant_id,
            resource_id=policy_input.resource.resource_id,
            matched_rule_ids=[],
            policy_version="forti-fail-closed-1.0.0",
            requires_approval=False,
            requires_simulation=policy_input.action_class
            in {ActionClass.EXECUTE_LOW, ActionClass.EXECUTE_HIGH, ActionClass.SIMULATE},
            evaluator=self._backend_name,
            metadata={"fail_closed": True},
        )

    def _to_decision(
        self,
        policy_input: PolicyInput,
        rule: PolicyRuleSpec,
    ) -> PolicyDecision:
        """Map a matched rule to a ``PolicyDecision``."""

        requires_approval = rule.requires_approval or (
            rule.verdict == PolicyVerdict.ESCALATE
        )
        return PolicyDecision(
            verdict=rule.verdict,
            reason=f"Matched policy rule '{rule.name}': {rule.description}",
            action_class=policy_input.action_class,
            tenant_id=policy_input.tenant_id,
            resource_id=policy_input.resource.resource_id,
            matched_rule_ids=[rule.rule_id],
            policy_version=rule.policy_version,
            requires_approval=requires_approval,
            requires_simulation=rule.requires_simulation,
            evaluator=self._backend_name,
            metadata={
                "rule_name": rule.name,
                "priority": rule.priority,
            },
        )

    def filter_matching(
        self,
        policy_input: PolicyInput,
        rules: Sequence[PolicyRuleSpec],
    ) -> List[PolicyRuleSpec]:
        """Return all matching rules (diagnostics / tests)."""

        return [rule for rule in rules if rule.enabled and self.matches(policy_input, rule)]
