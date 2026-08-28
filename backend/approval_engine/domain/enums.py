"""Domain enums for the Enterprise Approval Engine."""

from __future__ import annotations

from enum import Enum


class ApprovalState(str, Enum):
    """Lifecycle state of an approval request / workflow."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    ESCALATED = "escalated"
    AUTO_APPROVED = "auto_approved"


class ApprovalType(str, Enum):
    """Classification of the approval gate."""

    SECURITY_REVIEW = "security_review"
    OPERATIONS_REVIEW = "operations_review"
    INFRASTRUCTURE_REVIEW = "infrastructure_review"
    COMPLIANCE_REVIEW = "compliance_review"
    EMERGENCY_CHANGE = "emergency_change"
    MANUAL_INVESTIGATION = "manual_investigation"


class ApprovalMode(str, Enum):
    """How stages within a workflow progress."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class ApproverRole(str, Enum):
    """Organizational roles used for routing."""

    SECURITY_MANAGER = "security_manager"
    INFRASTRUCTURE_MANAGER = "infrastructure_manager"
    NETWORK_TEAM = "network_team"
    SECURITY_APPROVER = "security_approver"
    OPERATIONS_MANAGER = "operations_manager"
    COMPLIANCE_OFFICER = "compliance_officer"
    CHANGE_MANAGER = "change_manager"
    BUSINESS_OWNER = "business_owner"
    DELEGATE = "delegate"
    EMERGENCY_APPROVER = "emergency_approver"


class StageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    EXPIRED = "expired"
    ESCALATED = "escalated"


class AssignmentStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DELEGATED = "delegated"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class NotificationKind(str, Enum):
    REQUESTED = "requested"
    REMINDER = "reminder"
    DECIDED = "decided"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    DELEGATED = "delegated"


class NotificationStatus(str, Enum):
    PREPARED = "prepared"
    SUPPRESSED = "suppressed"


class AuditAction(str, Enum):
    REQUEST_CREATED = "request_created"
    REQUEST_UPDATED = "request_updated"
    DECISION_RECORDED = "decision_recorded"
    AUTO_APPROVED = "auto_approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    ESCALATED = "escalated"
    DELEGATED = "delegated"
    COMMENT_ADDED = "comment_added"
    POLICY_EVALUATED = "policy_evaluated"
    WORKFLOW_ADVANCED = "workflow_advanced"
    AUTHORIZATION_ISSUED = "authorization_issued"
    SEARCHED = "searched"
    HISTORY_RECORDED = "history_recorded"
    NOTIFICATION_PREPARED = "notification_prepared"
    REPLAYED = "replayed"


class PolicyMatchMode(str, Enum):
    ALL = "all"  # AND
    ANY = "any"  # OR
