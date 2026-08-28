"""
Policy evaluation backends (local rules today, OPA-ready tomorrow).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from policy_engine.models import PolicyDecision, PolicyInput, PolicyRuleSpec


class PolicyBackend(ABC):
    """
    Provider-independent policy evaluation backend.

    ``LocalRuleBackend`` implements in-process rules. ``OpaPolicyBackend`` is
    a future integration point that must return the same ``PolicyDecision``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier recorded on ``PolicyDecision.evaluator``."""

    @abstractmethod
    def evaluate(self, policy_input: PolicyInput) -> PolicyDecision:
        """Evaluate input and return an authoritative decision."""


class RuleRepository(ABC):
    """Abstraction over policy rule storage (memory, DB, OPA bundle, …)."""

    @abstractmethod
    def list_rules(self, tenant_id: Optional[str] = None) -> Sequence[PolicyRuleSpec]:
        """Return enabled rules applicable to a tenant context."""
