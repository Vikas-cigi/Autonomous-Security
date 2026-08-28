"""Core Enterprise Verification Engine domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from models.enums import VerificationStatus as CanonicalVerificationStatus
from models.verification import (
    VerificationCheck as CanonicalVerificationCheck,
    VerificationObject,
)
from verification_engine.domain.enums import (
    CheckResultStatus,
    CheckType,
    ClosureRecommendation,
    FindingDisposition,
    VerificationEventType,
    VerificationStatus,
)

ALGORITHM_VERSION = "1.0.0"
VERIFIER_NAME = "xolaris.verification_engine"


class VerificationEvidence(FortiBaseModel):
    evidence_id: UUID = Field(default_factory=new_id)
    phase: str = Field(..., min_length=1, max_length=32)  # pre | post | rescan
    kind: str = Field(default="observation", max_length=64)
    summary: str = Field(..., min_length=1, max_length=2000)
    source: Optional[str] = Field(default=None, max_length=128)
    indicates_resolved: Optional[bool] = None
    attributes: Dict[str, str] = Field(default_factory=dict)
    collected_at: datetime = Field(default_factory=utc_now)

    @field_validator("collected_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class VerificationCheck(FortiBaseModel):
    check_id: UUID = Field(default_factory=new_id)
    check_type: CheckType = Field(...)
    name: str = Field(..., min_length=1, max_length=256)
    status: CheckResultStatus = Field(...)
    passed: bool = Field(...)
    details: str = Field(..., min_length=1, max_length=4000)
    evidence_ids: List[UUID] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class VerificationComparison(FortiBaseModel):
    pre_evidence_count: int = Field(..., ge=0)
    post_evidence_count: int = Field(..., ge=0)
    resolved_signals: int = Field(default=0, ge=0)
    unresolved_signals: int = Field(default=0, ge=0)
    rescan_finding_present: Optional[bool] = None
    pre_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    post_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    risk_reduction_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=1, max_length=4000)


class VerificationFinding(FortiBaseModel):
    finding_id: UUID = Field(...)
    prior_status: str = Field(..., max_length=32)
    disposition: FindingDisposition = Field(...)
    recommended_status: str = Field(..., max_length=32)
    rationale: str = Field(..., min_length=1, max_length=2000)


class VerificationPlan(FortiBaseModel):
    """Ordered set of checks to run for this verification."""

    checks: List[CheckType] = Field(default_factory=list)
    require_rescan: bool = Field(default=True)
    require_compliance: bool = Field(default=False)
    require_service_check: bool = Field(default=True)


class VerificationTimeline(FortiBaseModel):
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    @field_validator(
        "queued_at", "started_at", "completed_at", "cancelled_at", mode="before"
    )
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class VerificationEvent(FortiBaseModel):
    id: UUID = Field(default_factory=new_id)
    verification_id: UUID = Field(...)
    event_type: VerificationEventType = Field(...)
    message: str = Field(..., min_length=1, max_length=2000)
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class VerificationMetrics(FortiBaseModel):
    total_checks: int = Field(default=0, ge=0)
    passed_checks: int = Field(default=0, ge=0)
    failed_checks: int = Field(default=0, ge=0)
    skipped_checks: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    evidence_compared: int = Field(default=0, ge=0)


class VerificationSummary(FortiBaseModel):
    headline: str = Field(..., min_length=1, max_length=512)
    details: str = Field(..., min_length=1, max_length=8000)
    success: bool = Field(...)
    closure_recommendation: ClosureRecommendation = Field(...)


class VerificationReport(FortiBaseModel):
    verification_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    execution_id: UUID = Field(...)
    status: VerificationStatus = Field(...)
    closure_recommendation: ClosureRecommendation = Field(...)
    finding_disposition: FindingDisposition = Field(...)
    comparison: VerificationComparison = Field(...)
    checks: List[VerificationCheck] = Field(default_factory=list)
    summary: str = Field(..., min_length=1, max_length=8000)
    generated_at: datetime = Field(default_factory=utc_now)

    @field_validator("generated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class VerificationResult(TimestampedModel):
    """
    Post-execution verification envelope.

    Confirms remediation effectiveness without executing remediation,
    recalculating risk, or invoking AI.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    execution_id: UUID = Field(...)
    plan_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    decision_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    status: VerificationStatus = Field(default=VerificationStatus.PENDING)
    plan: VerificationPlan = Field(...)
    checks: List[VerificationCheck] = Field(default_factory=list)
    evidence: List[VerificationEvidence] = Field(default_factory=list)
    comparison: Optional[VerificationComparison] = None
    finding: Optional[VerificationFinding] = None
    timeline: VerificationTimeline = Field(default_factory=VerificationTimeline)
    events: List[VerificationEvent] = Field(default_factory=list)
    metrics: VerificationMetrics = Field(default_factory=VerificationMetrics)
    summary: Optional[VerificationSummary] = None
    report: Optional[VerificationReport] = None
    closure_recommendation: Optional[ClosureRecommendation] = None
    operator: Optional[str] = Field(default=None, max_length=256)
    algorithm_version: str = Field(default=ALGORITHM_VERSION, max_length=32)
    current_version: int = Field(default=1, ge=1)
    first_started_at: Optional[datetime] = None
    last_evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("first_started_at", "last_evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            VerificationStatus.VERIFIED,
            VerificationStatus.FAILED,
            VerificationStatus.REOPENED,
            VerificationStatus.ESCALATED,
            VerificationStatus.CANCELLED,
            VerificationStatus.COMPLETED,
        }

    def to_canonical_verification_object(
        self,
        *,
        remediation_id: Optional[UUID] = None,
    ) -> VerificationObject:
        if self.status == VerificationStatus.VERIFIED:
            status = CanonicalVerificationStatus.PASSED
        elif self.status in {
            VerificationStatus.FAILED,
            VerificationStatus.REOPENED,
            VerificationStatus.ESCALATED,
        }:
            # reopen/escalate map to failed verification gate
            if self.checks and any(c.passed for c in self.checks) and not all(
                c.passed for c in self.checks
            ):
                status = CanonicalVerificationStatus.PARTIAL
            else:
                status = CanonicalVerificationStatus.FAILED
        elif self.status == VerificationStatus.CANCELLED:
            status = CanonicalVerificationStatus.SKIPPED
        elif self.status == VerificationStatus.COMPLETED:
            status = CanonicalVerificationStatus.PARTIAL
        elif self.status == VerificationStatus.RUNNING:
            status = CanonicalVerificationStatus.IN_PROGRESS
        else:
            status = CanonicalVerificationStatus.NOT_STARTED

        canonical_checks = [
            CanonicalVerificationCheck(
                check_id=c.check_id,
                name=c.name,
                passed=c.passed,
                details=c.details,
                evidence_ids=list(c.evidence_ids),
            )
            for c in self.checks
            if c.status != CheckResultStatus.SKIPPED
        ]

        # Ensure status consistency for PASSED/FAILED/PARTIAL
        if status == CanonicalVerificationStatus.PASSED and not canonical_checks:
            status = CanonicalVerificationStatus.NOT_STARTED
        if status == CanonicalVerificationStatus.PASSED and not all(
            c.passed for c in canonical_checks
        ):
            status = CanonicalVerificationStatus.PARTIAL
        if (
            status == CanonicalVerificationStatus.FAILED
            and canonical_checks
            and all(c.passed for c in canonical_checks)
        ):
            status = CanonicalVerificationStatus.PARTIAL

        residual = None
        if self.comparison and self.comparison.post_risk_score is not None:
            residual = min(1.0, max(0.0, self.comparison.post_risk_score / 100.0))

        return VerificationObject(
            id=self.id,
            remediation_id=remediation_id,
            finding_id=self.finding_id,
            status=status,
            checks=canonical_checks,
            evidence=[],
            verifier=self.operator or VERIFIER_NAME,
            started_at=self.timeline.started_at or self.first_started_at,
            completed_at=self.timeline.completed_at,
            residual_risk=residual,
            metadata={
                "engine_status": self.status.value,
                "closure_recommendation": (
                    self.closure_recommendation.value
                    if self.closure_recommendation
                    else ""
                ),
                "algorithm_version": self.algorithm_version,
            },
        )
