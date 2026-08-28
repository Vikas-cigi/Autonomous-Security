"""
Canonical RemediationObject — governed fix plans with rollback and verification.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import ActorReference, FortiBaseModel, TimestampedModel, new_id, utc_now
from models.enums import ApprovalStatus, ExecutionStatus, SimulationStatus, VerificationStatus
from models.simulation import SimulationObject
from models.verification import VerificationObject


class RemediationStep(FortiBaseModel):
    """Ordered step inside a remediation or rollback plan."""

    step_id: UUID = Field(default_factory=new_id, description="Step identifier.")
    sequence: int = Field(..., ge=1, description="1-based execution order.")
    action: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Canonical action description (not a raw vendor command blob).",
    )
    target: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Target resource or control plane reference.",
    )
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=86400,
        description="Step timeout in seconds.",
    )
    is_destructive: bool = Field(
        default=False,
        description="Whether the step can cause irreversible change.",
    )
    parameters: dict = Field(
        default_factory=dict,
        description="Structured parameters; forbid embedding raw scanner payloads.",
    )

    @field_validator("parameters")
    @classmethod
    def limit_parameters(cls, value: dict) -> dict:
        """Cap parameter map size."""

        if len(value) > 64:
            raise ValueError("step parameters limited to 64 keys")
        return value


class RemediationPlan(FortiBaseModel):
    """Forward remediation plan composed of ordered steps."""

    plan_id: UUID = Field(default_factory=new_id, description="Plan identifier.")
    summary: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="High-level plan summary.",
    )
    steps: List[RemediationStep] = Field(
        ...,
        min_length=1,
        description="Ordered remediation steps.",
    )
    estimated_duration_seconds: int = Field(
        default=300,
        ge=1,
        description="Estimated total execution time.",
    )

    @field_validator("steps")
    @classmethod
    def validate_step_order(cls, value: List[RemediationStep]) -> List[RemediationStep]:
        """Require unique sequences starting at 1."""

        sequences = [step.sequence for step in value]
        if len(sequences) != len(set(sequences)):
            raise ValueError("remediation step sequences must be unique")
        if sorted(sequences) != list(range(1, len(sequences) + 1)):
            raise ValueError("remediation step sequences must be contiguous from 1")
        return sorted(value, key=lambda step: step.sequence)


class RollbackPlan(FortiBaseModel):
    """Compensating plan to undo a failed or undesired remediation."""

    plan_id: UUID = Field(default_factory=new_id, description="Rollback plan id.")
    summary: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Rollback summary.",
    )
    steps: List[RemediationStep] = Field(
        ...,
        min_length=1,
        description="Ordered rollback steps.",
    )
    automatic: bool = Field(
        default=False,
        description="Whether rollback may execute without additional approval.",
    )

    @field_validator("steps")
    @classmethod
    def validate_step_order(cls, value: List[RemediationStep]) -> List[RemediationStep]:
        """Require unique contiguous sequences."""

        sequences = [step.sequence for step in value]
        if len(sequences) != len(set(sequences)):
            raise ValueError("rollback step sequences must be unique")
        if sorted(sequences) != list(range(1, len(sequences) + 1)):
            raise ValueError("rollback step sequences must be contiguous from 1")
        return sorted(value, key=lambda step: step.sequence)


class ApprovalRecord(FortiBaseModel):
    """Approval gate for remediation execution."""

    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        description="Approval status.",
    )
    requested_at: datetime = Field(
        default_factory=utc_now,
        description="UTC time approval was requested.",
    )
    decided_at: Optional[datetime] = Field(
        default=None,
        description="UTC time approval was decided.",
    )
    approver: Optional[ActorReference] = Field(
        default=None,
        description="Approving actor when decided.",
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="Approver comment.",
    )

    @field_validator("requested_at", "decided_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware datetimes."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def approval_consistency(self) -> ApprovalRecord:
        """Approved/rejected records need approver and decided_at."""

        if self.status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            if self.approver is None:
                raise ValueError(f"{self.status.value} approval requires approver")
            if self.decided_at is None:
                raise ValueError(f"{self.status.value} approval requires decided_at")
        if self.decided_at is not None and self.decided_at < self.requested_at:
            raise ValueError("decided_at cannot be before requested_at")
        return self


class RemediationObject(TimestampedModel):
    """
    Canonical remediation case binding plan, simulation, approval, and verification.

    Execution engines operate exclusively on this model — never on raw scanner
    output or untyped dictionaries.
    """

    id: UUID = Field(default_factory=new_id, description="Remediation identifier.")
    tenant_id: UUID = Field(..., description="Owning tenant.")
    finding_id: UUID = Field(..., description="Finding being remediated.")
    decision_id: UUID = Field(
        ...,
        description="DecisionObject that authorized this remediation.",
    )
    plan: RemediationPlan = Field(..., description="Forward remediation plan.")
    rollback_plan: RollbackPlan = Field(..., description="Compensating rollback plan.")
    simulation: SimulationObject = Field(
        ...,
        description="Pre-execution simulation record.",
    )
    approval: ApprovalRecord = Field(
        default_factory=ApprovalRecord,
        description="Approval gate state.",
    )
    verification: Optional[VerificationObject] = Field(
        default=None,
        description="Post-execution verification record when available.",
    )
    execution_status: ExecutionStatus = Field(
        default=ExecutionStatus.PENDING,
        description="Remediation execution lifecycle status.",
    )
    started_at: Optional[datetime] = Field(default=None, description="UTC start time.")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="UTC completion time.",
    )

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware datetimes."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def link_child_ids(self) -> RemediationObject:
        """Keep nested simulation/verification remediation_id aligned when set."""

        if (
            self.simulation.remediation_id is not None
            and self.simulation.remediation_id != self.id
        ):
            raise ValueError("simulation.remediation_id must match remediation id")
        if (
            self.verification is not None
            and self.verification.remediation_id is not None
            and self.verification.remediation_id != self.id
        ):
            raise ValueError("verification.remediation_id must match remediation id")
        if (
            self.verification is not None
            and self.verification.finding_id != self.finding_id
        ):
            raise ValueError("verification.finding_id must match remediation finding_id")
        return self

    @model_validator(mode="after")
    def execution_gate_rules(self) -> RemediationObject:
        """Enforce simulation/approval gates before running/succeeding."""

        if self.execution_status in {
            ExecutionStatus.RUNNING,
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.QUEUED,
        }:
            if self.approval.status not in {
                ApprovalStatus.APPROVED,
                ApprovalStatus.NOT_REQUIRED,
            }:
                raise ValueError(
                    "execution requires approval status approved or not_required"
                )
            destructive = any(step.is_destructive for step in self.plan.steps)
            if destructive and self.simulation.status != SimulationStatus.PASSED:
                raise ValueError(
                    "destructive remediations require a PASSED simulation"
                )

        if self.execution_status == ExecutionStatus.SUCCEEDED:
            if self.verification is None:
                raise ValueError("SUCCEEDED remediations require verification")
            if self.verification.status != VerificationStatus.PASSED:
                raise ValueError(
                    "SUCCEEDED remediations require PASSED verification"
                )
            if self.completed_at is None:
                raise ValueError("SUCCEEDED remediations require completed_at")

        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")

        return self
