"""
PolicyEngine — entry point for authorizing Forti-ai security actions.
"""

from __future__ import annotations

import logging
from typing import Optional

from models.enums import ActionClass, PolicyVerdict
from policy_engine.backends.base import PolicyBackend
from policy_engine.backends.local import LocalRuleBackend
from policy_engine.evaluator import PolicyEvaluator
from policy_engine.exceptions import PolicyConfigurationError, PolicyEvaluationError
from policy_engine.models import PolicyDecision, PolicyInput

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Evaluates every security action before it may proceed.

    Responsibilities:
        - Require a policy backend (never act without policy configuration)
        - Delegate matching to ``PolicyEvaluator`` via the backend
        - Fail closed on backend / configuration errors
        - Return only ``PolicyDecision``

    Independent of LLM providers, UI, and AI orchestration layers.
    """

    def __init__(
        self,
        backend: Optional[PolicyBackend] = None,
        *,
        fallback_deny_on_error: bool = True,
    ) -> None:
        """
        Args:
            backend: Policy backend (defaults to ``LocalRuleBackend``).
            fallback_deny_on_error: When True, evaluation errors become DENY
                decisions instead of raising (fail closed).
        """

        self._backend = backend or LocalRuleBackend()
        self._fallback_deny_on_error = fallback_deny_on_error
        self._evaluator = PolicyEvaluator(backend_name="engine-fail-closed")
        logger.debug(
            "PolicyEngine initialized backend=%s fail_closed=%s",
            self._backend.name,
            fallback_deny_on_error,
        )

    @property
    def backend(self) -> PolicyBackend:
        """Return the active policy backend."""

        return self._backend

    def evaluate(self, policy_input: PolicyInput) -> PolicyDecision:
        """
        Evaluate a requested action and return ``PolicyDecision``.

        Raises:
            PolicyConfigurationError: When fail-closed fallback is disabled and
                the backend is misconfigured.
            PolicyEvaluationError: When fail-closed fallback is disabled and
                evaluation fails.
        """

        logger.info(
            "PolicyEngine.evaluate action=%s tenant=%s resource=%s backend=%s",
            policy_input.action_class.value,
            policy_input.tenant_id,
            policy_input.resource.resource_id,
            self._backend.name,
        )

        try:
            decision = self._backend.evaluate(policy_input)
        except (PolicyConfigurationError, PolicyEvaluationError) as exc:
            logger.error("Policy evaluation failed: %s", exc)
            if not self._fallback_deny_on_error:
                raise
            return self._fail_closed_decision(policy_input, str(exc))

        self._assert_safe_decision(policy_input, decision)
        logger.info(
            "PolicyEngine decision verdict=%s rule_ids=%s",
            decision.verdict.value,
            [str(item) for item in decision.matched_rule_ids],
        )
        return decision

    def authorize(self, policy_input: PolicyInput) -> PolicyDecision:
        """
        Alias of ``evaluate`` emphasizing mandatory pre-execution checks.

        Callers performing EXECUTE_* MUST invoke this and honor the verdict.
        """

        return self.evaluate(policy_input)

    def is_execution_allowed(self, decision: PolicyDecision) -> bool:
        """
        Return True only when immediate execution is authorized.

        ``ESCALATE`` is not execution approval — callers must obtain a human
        decision and re-enter with an approved control plane action.
        """

        return decision.verdict == PolicyVerdict.ALLOW

    def _assert_safe_decision(
        self,
        policy_input: PolicyInput,
        decision: PolicyDecision,
    ) -> None:
        """Guardrail: execute ALLOW must always cite a matched rule."""

        if decision.verdict != PolicyVerdict.ALLOW:
            return
        if policy_input.action_class in {
            ActionClass.EXECUTE_LOW,
            ActionClass.EXECUTE_HIGH,
        } and not decision.matched_rule_ids:
            raise PolicyEvaluationError(
                "Refusing ALLOW execute decision without matched policy rule.",
                details={"action_class": policy_input.action_class.value},
            )

    def _fail_closed_decision(
        self,
        policy_input: PolicyInput,
        error: str,
    ) -> PolicyDecision:
        """Convert backend failure into an explicit DENY decision."""

        decision = self._evaluator.deny_without_policy(policy_input)
        return decision.model_copy(
            update={
                "reason": f"Denied: policy evaluation error ({error})",
                "metadata": {
                    **decision.metadata,
                    "evaluation_error": error,
                    "backend": self._backend.name,
                },
                "evaluator": self._backend.name,
            }
        )
