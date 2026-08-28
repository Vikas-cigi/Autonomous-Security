"""
Policy Engine package — authorize every Forti-ai security action.

No UI. No AI. Provider-independent business logic only.
"""

from models.enums import ActionClass, PolicyVerdict
from policy_engine.engine import PolicyEngine
from policy_engine.evaluator import PolicyEvaluator
from policy_engine.exceptions import (
    PolicyConfigurationError,
    PolicyEngineError,
    PolicyEvaluationError,
)
from policy_engine.models import (
    PolicyDecision,
    PolicyInput,
    PolicyRuleSpec,
    ResourceRef,
)

__all__ = [
    "ActionClass",
    "PolicyConfigurationError",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyEngineError",
    "PolicyEvaluationError",
    "PolicyEvaluator",
    "PolicyInput",
    "PolicyRuleSpec",
    "PolicyVerdict",
    "ResourceRef",
]

__version__ = "1.0.0"
