"""
Canonical VerificationObject — post-remediation proof of effectiveness.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, new_id, utc_now
from models.enums import VerificationStatus
from models.evidence import EvidenceObject


class VerificationCheck(FortiBaseModel):
    """Atomic verification assertion executed after remediation."""

    check_id: UUID = Field(default_factory=new_id, description="Check identifier.")
    name: str = Field(..., min_length=1, max_length=256, description="Check name.")
    passed: bool = Field(..., description="Whether the check passed.")
    details: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Canonical explanation of the check result.",
    )
    evidence_ids: List[UUID] = Field(
        default_factory=list,
        description="EvidenceObject ids supporting this check.",
    )

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, value: List[UUID]) -> List[UUID]:
        """Disallow duplicate evidence references."""

        if len(value) != len(set(value)):
            raise ValueError("evidence_ids must be unique")
        return value


class VerificationObject(FortiBaseModel):
    """
    Post-change verification record proving remediation effectiveness.

    Verification consumes canonical evidence, never raw scanner dumps.
    """

    id: UUID = Field(default_factory=new_id, description="Verification identifier.")
    remediation_id: Optional[UUID] = Field(
        default=None,
        description="Owning remediation id when linked.",
    )
    finding_id: UUID = Field(
        ...,
        description="Finding being verified as remediated or mitigated.",
    )
    status: VerificationStatus = Field(
        default=VerificationStatus.NOT_STARTED,
        description="Verification lifecycle status.",
    )
    checks: List[VerificationCheck] = Field(
        default_factory=list,
        description="Individual verification assertions.",
    )
    evidence: List[EvidenceObject] = Field(
        default_factory=list,
        description="Canonical evidence collected during verification.",
    )
    verifier: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Verification engine, playbook, or human verifier identity.",
    )
    started_at: Optional[datetime] = Field(default=None, description="UTC start time.")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="UTC completion time.",
    )
    residual_risk: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Estimated residual risk after verification.",
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Small operational metadata.",
    )

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware datetimes."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @field_validator("checks")
    @classmethod
    def unique_checks(cls, value: List[VerificationCheck]) -> List[VerificationCheck]:
        """Enforce unique check ids."""

        ids = [check.check_id for check in value]
        if len(ids) != len(set(ids)):
            raise ValueError("verification check_id values must be unique")
        return value

    @field_validator("evidence")
    @classmethod
    def unique_evidence_objects(
        cls,
        value: List[EvidenceObject],
    ) -> List[EvidenceObject]:
        """Enforce unique evidence object ids."""

        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("verification evidence ids must be unique")
        return value

    @model_validator(mode="after")
    def status_consistency(self) -> VerificationObject:
        """Align status with checks and timestamps."""

        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")

        if self.status == VerificationStatus.PASSED:
            if not self.checks:
                raise ValueError("PASSED verification requires at least one check")
            if not all(check.passed for check in self.checks):
                raise ValueError("PASSED verification requires all checks to pass")
            if self.completed_at is None:
                raise ValueError("PASSED verification requires completed_at")

        if self.status == VerificationStatus.FAILED:
            if self.checks and all(check.passed for check in self.checks):
                raise ValueError("FAILED verification cannot have all checks passing")
            if self.completed_at is None:
                raise ValueError("FAILED verification requires completed_at")

        if self.status == VerificationStatus.PARTIAL:
            if not self.checks:
                raise ValueError("PARTIAL verification requires checks")
            passed = sum(1 for check in self.checks if check.passed)
            if passed == 0 or passed == len(self.checks):
                raise ValueError(
                    "PARTIAL verification requires a mix of passed and failed checks"
                )

        return self

    def derive_status_from_checks(self) -> VerificationStatus:
        """Compute a status suggestion from current checks."""

        if not self.checks:
            return VerificationStatus.NOT_STARTED
        passed = [check.passed for check in self.checks]
        if all(passed):
            return VerificationStatus.PASSED
        if not any(passed):
            return VerificationStatus.FAILED
        return VerificationStatus.PARTIAL
