"""
Repository-layer enumerations.

Lifecycle buckets map onto canonical ``FindingStatus`` without mutating
``models.enums``.
"""

from __future__ import annotations

from enum import Enum

from models.enums import FindingStatus


class LifecycleState(str, Enum):
    """
    Product-facing finding lifecycle.

    Mapped to canonical ``FindingStatus`` values for storage compatibility.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"


class AuditAction(str, Enum):
    """Audit events emitted by the Evidence Repository."""

    FINDING_CREATED = "finding_created"
    FINDING_UPDATED = "finding_updated"
    FINDING_STATUS_CHANGED = "finding_status_changed"
    FINDING_VERSIONED = "finding_versioned"
    EVIDENCE_ATTACHED = "evidence_attached"
    EVIDENCE_VERSIONED = "evidence_versioned"
    DEDUPLICATED = "deduplicated"
    CORRELATED = "correlated"
    SEARCHED = "searched"


# Canonical status → lifecycle bucket
_STATUS_TO_LIFECYCLE: dict[FindingStatus, LifecycleState] = {
    FindingStatus.NEW: LifecycleState.OPEN,
    FindingStatus.TRIAGED: LifecycleState.OPEN,
    FindingStatus.REOPENED: LifecycleState.OPEN,
    FindingStatus.IN_REVIEW: LifecycleState.IN_PROGRESS,
    FindingStatus.APPROVED_FOR_REMEDIATION: LifecycleState.IN_PROGRESS,
    FindingStatus.REMEDIATING: LifecycleState.IN_PROGRESS,
    FindingStatus.VERIFYING: LifecycleState.IN_PROGRESS,
    FindingStatus.RESOLVED: LifecycleState.RESOLVED,
    FindingStatus.ACCEPTED_RISK: LifecycleState.ACCEPTED_RISK,
    FindingStatus.FALSE_POSITIVE: LifecycleState.FALSE_POSITIVE,
    FindingStatus.SUPPRESSED: LifecycleState.FALSE_POSITIVE,
}

# Lifecycle bucket → preferred canonical status when writing
_LIFECYCLE_TO_STATUS: dict[LifecycleState, FindingStatus] = {
    LifecycleState.OPEN: FindingStatus.NEW,
    LifecycleState.IN_PROGRESS: FindingStatus.REMEDIATING,
    LifecycleState.RESOLVED: FindingStatus.RESOLVED,
    LifecycleState.ACCEPTED_RISK: FindingStatus.ACCEPTED_RISK,
    LifecycleState.FALSE_POSITIVE: FindingStatus.FALSE_POSITIVE,
}


def to_lifecycle(status: FindingStatus) -> LifecycleState:
    """Map canonical finding status to product lifecycle bucket."""

    return _STATUS_TO_LIFECYCLE.get(status, LifecycleState.OPEN)


def to_finding_status(lifecycle: LifecycleState) -> FindingStatus:
    """Map product lifecycle bucket to a canonical finding status."""

    return _LIFECYCLE_TO_STATUS[lifecycle]


def statuses_for_lifecycle(lifecycle: LifecycleState) -> tuple[FindingStatus, ...]:
    """Return all canonical statuses that belong to a lifecycle bucket."""

    return tuple(
        status
        for status, bucket in _STATUS_TO_LIFECYCLE.items()
        if bucket is lifecycle
    )
