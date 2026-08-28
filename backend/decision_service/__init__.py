"""
Enterprise Decision Service.

Orchestrates Evidence, Asset Inventory, Threat Intelligence, Trust Scoring,
Risk Engine, and Policy Engine snapshots, then optionally invokes Architecture
V2 Context Manager → Prompt Builder → Provider Factory to produce a canonical
DecisionObject.

Pipeline position: after Risk Engine, before Remediation Planner.

Distinct from ``decision_engine`` (AI intent routing CHAT/TOOL/RAG).
Does not modify existing platform modules. No REST APIs.
"""

from decision_service.di.container import DecisionServiceBundle, DecisionServiceContainer
from decision_service.domain.enums import (
    DecisionLifecycleStatus,
    DecisionSource,
    SecurityDecisionType,
)
from decision_service.domain.history import DecisionAuditRecord, DecisionVersionRecord
from decision_service.domain.inputs import DecisionRequest
from decision_service.domain.models import (
    AIRequestEnvelope,
    AIResponseEnvelope,
    DecisionContext,
    DecisionExplanation,
    DecisionReasoning,
    DecisionRecommendation,
    DecisionResponse,
)
from decision_service.interfaces.ai_gateway import AIDecisionGateway
from decision_service.interfaces.decision_audit_repository import DecisionAuditRepository
from decision_service.interfaces.decision_repository import DecisionRepository
from decision_service.services.decision_service import DecisionService

__all__ = [
    "AIDecisionGateway",
    "AIRequestEnvelope",
    "AIResponseEnvelope",
    "DecisionAuditRecord",
    "DecisionAuditRepository",
    "DecisionContext",
    "DecisionExplanation",
    "DecisionLifecycleStatus",
    "DecisionReasoning",
    "DecisionRecommendation",
    "DecisionRepository",
    "DecisionRequest",
    "DecisionResponse",
    "DecisionService",
    "DecisionServiceBundle",
    "DecisionServiceContainer",
    "DecisionSource",
    "DecisionVersionRecord",
    "SecurityDecisionType",
]

__version__ = "1.0.0"
