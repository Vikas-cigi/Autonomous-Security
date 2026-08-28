"""
OPA policy backend — integration seam for future Open Policy Agent.

This module does **not** call OPA yet. It defines the contract so the
``PolicyEngine`` can swap backends without changing business callers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from policy_engine.backends.base import PolicyBackend
from policy_engine.exceptions import PolicyEvaluationError
from policy_engine.models import PolicyDecision, PolicyInput

logger = logging.getLogger(__name__)


class OpaPolicyBackend(PolicyBackend):
    """
    Future OPA/Rego evaluation backend.

    Expected production wiring:
        - POST ``/v1/data/forti/authz/decision`` with ``PolicyInput`` as input
        - Map OPA JSON to ``PolicyDecision`` (ALLOW | DENY | ESCALATE)

    Until configured, ``evaluate`` fails closed via ``PolicyEvaluationError``,
    which ``PolicyEngine`` converts into a DENY decision.
    """

    def __init__(
        self,
        *,
        opa_url: Optional[str] = None,
        policy_path: str = "forti/authz/decision",
        timeout_seconds: float = 3.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.opa_url = opa_url
        self.policy_path = policy_path
        self.timeout_seconds = timeout_seconds
        self.headers = headers or {}

    @property
    def name(self) -> str:
        return "opa"

    def evaluate(self, policy_input: PolicyInput) -> PolicyDecision:
        """
        Evaluate via OPA when configured.

        Raises:
            PolicyEvaluationError: Always today — OPA transport not enabled.
        """

        if not self.opa_url:
            logger.error("OPA backend invoked without opa_url; failing closed")
            raise PolicyEvaluationError(
                "OPA backend is not configured (opa_url missing).",
                details={"backend": self.name, "policy_path": self.policy_path},
            )

        # Intentionally unimplemented transport — keep provider-independent
        # until OPA is adopted. Do not silently allow.
        logger.error(
            "OPA backend transport not implemented; refusing action=%s",
            policy_input.action_class.value,
        )
        raise PolicyEvaluationError(
            "OPA backend transport is not implemented yet; failing closed.",
            details={
                "backend": self.name,
                "opa_url": self.opa_url,
                "policy_path": self.policy_path,
                "input_action": policy_input.action_class.value,
            },
        )

    def build_opa_input(self, policy_input: PolicyInput) -> Dict[str, Any]:
        """
        Serialize ``PolicyInput`` into an OPA-friendly document.

        Exposed for contract tests and future HTTP wiring.
        """

        return {
            "tenant_id": str(policy_input.tenant_id),
            "user": policy_input.user.model_dump(mode="json"),
            "roles": policy_input.roles,
            "scope": policy_input.scope.value,
            "action_class": policy_input.action_class.value,
            "resource": policy_input.resource.model_dump(mode="json"),
            "finding": (
                policy_input.finding.model_dump(mode="json")
                if policy_input.finding is not None
                else None
            ),
            "attributes": policy_input.attributes,
        }
