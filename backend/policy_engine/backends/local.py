"""
In-process policy backend using ``PolicyEvaluator`` + rule repository.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from policy_engine.backends.base import PolicyBackend, RuleRepository
from policy_engine.default_rules import default_policy_rules
from policy_engine.evaluator import PolicyEvaluator
from policy_engine.exceptions import PolicyConfigurationError
from policy_engine.models import PolicyDecision, PolicyInput, PolicyRuleSpec

logger = logging.getLogger(__name__)


class InMemoryRuleRepository(RuleRepository):
    """Simple rule store suitable for tests and default engine wiring."""

    def __init__(self, rules: Optional[Sequence[PolicyRuleSpec]] = None) -> None:
        self._rules: List[PolicyRuleSpec] = list(rules or default_policy_rules())

    def list_rules(self, tenant_id: Optional[str] = None) -> Sequence[PolicyRuleSpec]:
        """Return all enabled rules (tenant filtering reserved for future)."""

        _ = tenant_id
        return [rule for rule in self._rules if rule.enabled]

    def add_rule(self, rule: PolicyRuleSpec) -> None:
        """Append a rule to the repository."""

        self._rules.append(rule)


class LocalRuleBackend(PolicyBackend):
    """Local deterministic policy backend (provider-independent)."""

    def __init__(
        self,
        repository: Optional[RuleRepository] = None,
        evaluator: Optional[PolicyEvaluator] = None,
    ) -> None:
        self._repository = repository or InMemoryRuleRepository()
        self._evaluator = evaluator or PolicyEvaluator(backend_name="local")

    @property
    def name(self) -> str:
        return "local"

    def evaluate(self, policy_input: PolicyInput) -> PolicyDecision:
        rules = list(self._repository.list_rules(str(policy_input.tenant_id)))
        if not rules:
            raise PolicyConfigurationError(
                "Local policy repository has no rules; refusing evaluation.",
                details={"backend": self.name},
            )
        logger.debug(
            "LocalRuleBackend evaluating action=%s rules=%s",
            policy_input.action_class.value,
            len(rules),
        )
        return self._evaluator.evaluate(policy_input, rules)
