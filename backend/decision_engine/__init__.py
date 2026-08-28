"""
Decision Engine package — Architecture V2 routing layer.

Public surface::

    from decision_engine import DecisionEngine, DecisionResult, DecisionType

Wired into ``LLMService`` when ``LLM_ENABLE_V2_STACK`` is True
(DecisionEngine → ContextManager → PromptBuilder → ProviderFactory).
"""

from decision_engine.decision_engine import DecisionEngine
from decision_engine.intent_router import IntentRouter
from decision_engine.models import DecisionResult, DecisionType

__all__ = [
    "DecisionEngine",
    "DecisionResult",
    "DecisionType",
    "IntentRouter",
]

__version__ = "0.1.0"
