"""
Canonical DecisionObject — governed security action decisions.

Distinct from the AI framework ``decision_engine.DecisionResult``. This model
captures human/policy/AI decisions about what to do with a finding.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import ActorReference, FortiBaseModel, new_id, utc_now
from models.enums import DecisionAction, Priority, RecommendedAction


class DecisionObject(FortiBaseModel):
    """
    Canonical decision record for a security finding or remediation case.

    ``decision`` is the authoritative action. ``recommended_action`` is the
    concrete operational step. Policy versioning and ownership support audit.
    """

    id: UUID = Field(
        default_factory=new_id,
        description="Canonical decision identifier.",
    )
    finding_id: UUID = Field(
        ...,
        description="Finding this decision applies to.",
    )
    tenant_id: UUID = Field(
        ...,
        description="Tenant scope for the decision.",
    )
    decision: DecisionAction = Field(
        ...,
        description="Authoritative decision action.",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="Justification for the decision (policy, risk, context).",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the decision correctness.",
    )
    recommended_action: RecommendedAction = Field(
        ...,
        description="Concrete recommended operational action.",
    )
    priority: Priority = Field(
        ...,
        description="Operational priority for execution.",
    )
    policy_version: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Version of the policy set that authorized this decision.",
    )
    owner: ActorReference = Field(
        ...,
        description="Accountable owner for the decision outcome.",
    )
    approver: Optional[ActorReference] = Field(
        default=None,
        description="Approver when four-eyes or policy approval is required.",
    )
    decided_at: datetime = Field(
        default_factory=utc_now,
        description="UTC timestamp when the decision was finalized.",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional expiry after which the decision must be re-evaluated.",
    )
    related_policy_ids: List[UUID] = Field(
        default_factory=list,
        description="PolicyObject ids evaluated while producing this decision.",
    )

    @field_validator("decided_at", "expires_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware datetimes."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @field_validator("policy_version")
    @classmethod
    def validate_policy_version(cls, value: str) -> str:
        """Require a non-empty semantic-ish policy version string."""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("policy_version is required")
        return cleaned

    @model_validator(mode="after")
    def expiry_after_decision(self) -> DecisionObject:
        """Ensure expiry is strictly after decision time when set."""

        if self.expires_at is not None and self.expires_at <= self.decided_at:
            raise ValueError("expires_at must be after decided_at")
        return self

    @model_validator(mode="after")
    def approval_rules(self) -> DecisionObject:
        """High-impact decisions require an approver distinct from the owner."""

        high_impact = {
            DecisionAction.REMEDIATE,
            DecisionAction.MITIGATE,
            DecisionAction.ACCEPT_RISK,
        }
        if self.decision in high_impact and self.priority in {Priority.P0, Priority.P1}:
            if self.approver is None:
                raise ValueError(
                    "P0/P1 remediate/mitigate/accept_risk decisions require an approver"
                )
            if self.approver.actor_id == self.owner.actor_id:
                raise ValueError("approver must be distinct from owner for P0/P1 decisions")
        return self

    @model_validator(mode="after")
    def action_alignment(self) -> DecisionObject:
        """Keep recommended_action coherent with decision class."""

        if (
            self.decision == DecisionAction.NO_ACTION
            and self.recommended_action
            not in {RecommendedAction.VERIFY_ONLY, RecommendedAction.MANUAL_REVIEW, RecommendedAction.OTHER}
        ):
            raise ValueError(
                "NO_ACTION decisions only allow verify_only, manual_review, or other"
            )
        if (
            self.decision == DecisionAction.REMEDIATE
            and self.recommended_action == RecommendedAction.VERIFY_ONLY
        ):
            raise ValueError("REMEDIATE cannot recommend verify_only")
        return self
