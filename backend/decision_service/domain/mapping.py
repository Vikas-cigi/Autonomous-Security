"""Map Enterprise Decision Service types onto canonical DecisionObject enums."""

from __future__ import annotations

from models.enums import DecisionAction, Priority, RecommendedAction
from decision_service.domain.enums import SecurityDecisionType


DECISION_TYPE_TO_ACTION: dict[SecurityDecisionType, DecisionAction] = {
    SecurityDecisionType.REMEDIATE: DecisionAction.REMEDIATE,
    SecurityDecisionType.IGNORE: DecisionAction.NO_ACTION,
    SecurityDecisionType.ESCALATE: DecisionAction.ESCALATE,
    SecurityDecisionType.INVESTIGATE: DecisionAction.INVESTIGATE,
    SecurityDecisionType.MONITOR: DecisionAction.MONITOR,
}

DECISION_TYPE_TO_RECOMMENDED: dict[SecurityDecisionType, RecommendedAction] = {
    SecurityDecisionType.REMEDIATE: RecommendedAction.APPLY_PATCH,
    SecurityDecisionType.IGNORE: RecommendedAction.VERIFY_ONLY,
    SecurityDecisionType.ESCALATE: RecommendedAction.MANUAL_REVIEW,
    SecurityDecisionType.INVESTIGATE: RecommendedAction.MANUAL_REVIEW,
    SecurityDecisionType.MONITOR: RecommendedAction.VERIFY_ONLY,
}

# Risk priority (P1–P5 from Risk Engine) → canonical Priority
RISK_PRIORITY_TO_CANONICAL: dict[str, Priority] = {
    "p1": Priority.P0,
    "p2": Priority.P1,
    "p3": Priority.P2,
    "p4": Priority.P3,
    "p5": Priority.P4,
}


def to_decision_action(decision_type: SecurityDecisionType) -> DecisionAction:
    return DECISION_TYPE_TO_ACTION[decision_type]


def to_recommended_action(
    decision_type: SecurityDecisionType,
    *,
    override: RecommendedAction | None = None,
) -> RecommendedAction:
    if override is not None:
        return override
    return DECISION_TYPE_TO_RECOMMENDED[decision_type]


def to_canonical_priority(risk_priority: str | None, risk_level: str | None) -> Priority:
    """Map Risk Engine priority/level onto canonical Priority."""

    if risk_priority:
        key = risk_priority.strip().lower()
        if key in RISK_PRIORITY_TO_CANONICAL:
            return RISK_PRIORITY_TO_CANONICAL[key]
    level = (risk_level or "").strip().lower()
    mapping = {
        "critical": Priority.P0,
        "high": Priority.P1,
        "medium": Priority.P2,
        "low": Priority.P3,
        "informational": Priority.P4,
    }
    return mapping.get(level, Priority.P3)
