"""Domain enums for the Enterprise Decision Service."""

from __future__ import annotations

from enum import Enum


class SecurityDecisionType(str, Enum):
    """
    Decision types produced by the Enterprise Decision Service.

    Distinct from ``decision_engine.DecisionType`` (AI intent routing).
    Maps onto canonical ``DecisionAction`` for ``DecisionObject`` emission.
    """

    REMEDIATE = "remediate"
    IGNORE = "ignore"
    ESCALATE = "escalate"
    INVESTIGATE = "investigate"
    MONITOR = "monitor"


class DecisionSource(str, Enum):
    """How the recommendation was produced."""

    AI = "ai"
    DETERMINISTIC = "deterministic"
    HYBRID = "hybrid"
    HUMAN = "human"


class DecisionLifecycleStatus(str, Enum):
    """Lifecycle of a persisted decision envelope."""

    DRAFT = "draft"
    PROPOSED = "proposed"
    POLICY_DENIED = "policy_denied"
    POLICY_ESCALATED = "policy_escalated"
    FINALIZED = "finalized"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


class AuditAction(str, Enum):
    """Audit actions for Decision Service operations."""

    REQUEST_RECEIVED = "request_received"
    CONTEXT_ASSEMBLED = "context_assembled"
    AI_INVOKED = "ai_invoked"
    AI_PARSED = "ai_parsed"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"
    POLICY_EVALUATED = "policy_evaluated"
    DECISION_CREATED = "decision_created"
    DECISION_UPDATED = "decision_updated"
    DECISION_FINALIZED = "decision_finalized"
    VALIDATION_FAILED = "validation_failed"
    SEARCHED = "searched"
    HISTORY_RECORDED = "history_recorded"
