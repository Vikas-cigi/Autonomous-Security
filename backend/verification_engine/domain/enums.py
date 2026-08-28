"""Domain enums for the Enterprise Verification Engine."""

from __future__ import annotations

from enum import Enum


class VerificationStatus(str, Enum):
    """Lifecycle state of a verification run."""

    PENDING = "pending"
    RUNNING = "running"
    VERIFIED = "verified"
    FAILED = "failed"
    REOPENED = "reopened"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class CheckType(str, Enum):
    FINDING_RESOLVED = "finding_resolved"
    CONFIGURATION_VALIDATED = "configuration_validated"
    SERVICE_AVAILABILITY = "service_availability"
    COMPLIANCE_VERIFIED = "compliance_verified"
    POLICY_COMPLIANCE = "policy_compliance"
    REMEDIATION_COMPLETED = "remediation_completed"
    ROLLBACK_VERIFICATION = "rollback_verification"
    INFRASTRUCTURE_VALIDATION = "infrastructure_validation"
    RISK_REDUCTION = "risk_reduction"
    RESCAN = "rescan"


class CheckResultStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"


class ClosureRecommendation(str, Enum):
    CLOSE_FINDING = "close_finding"
    REOPEN_FINDING = "reopen_finding"
    ESCALATE_FINDING = "escalate_finding"
    MANUAL_INVESTIGATION = "manual_investigation"
    ADDITIONAL_REMEDIATION_REQUIRED = "additional_remediation_required"


class FindingDisposition(str, Enum):
    UNCHANGED = "unchanged"
    CLOSE = "close"
    REOPEN = "reopen"
    ESCALATE = "escalate"


class VerificationEventType(str, Enum):
    CREATED = "created"
    STARTED = "started"
    CHECK_PASSED = "check_passed"
    CHECK_FAILED = "check_failed"
    RESCAN_COMPLETED = "rescan_completed"
    COMPARISON_COMPLETED = "comparison_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    REOPENED = "reopened"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    REPLAYED = "replayed"


class AuditAction(str, Enum):
    VERIFICATION_CREATED = "verification_created"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_CANCELLED = "verification_cancelled"
    CHECK_RECORDED = "check_recorded"
    EVIDENCE_RECORDED = "evidence_recorded"
    ESCALATED = "escalated"
    REOPENED = "reopened"
    SEARCHED = "searched"
    HISTORY_RECORDED = "history_recorded"
    REPLAYED = "replayed"
