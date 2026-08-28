"""
Canonical PolicyObject — versioned guardrails for decisions and remediations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from models.enums import PolicyEffect, PolicyScope, Severity


class PolicyCondition(FortiBaseModel):
    """Declarative match condition evaluated against canonical finding fields."""

    field: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Canonical field path, e.g. severity or finding_type.",
    )
    operator: str = Field(
        ...,
        description="Comparison operator: eq | neq | in | gte | lte | contains.",
    )
    value: Any = Field(
        ...,
        description="Expected value or list of values for the operator.",
    )

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, value: str) -> str:
        """Restrict operators to the supported set."""

        allowed = {"eq", "neq", "in", "gte", "lte", "contains"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"operator must be one of {sorted(allowed)}")
        return normalized


class PolicyRule(FortiBaseModel):
    """Single evaluable rule within a policy document."""

    rule_id: UUID = Field(default_factory=new_id, description="Stable rule id.")
    name: str = Field(..., min_length=1, max_length=256, description="Rule name.")
    effect: PolicyEffect = Field(..., description="Effect when the rule matches.")
    conditions: List[PolicyCondition] = Field(
        ...,
        min_length=1,
        description="All conditions must match (logical AND).",
    )
    min_severity: Optional[Severity] = Field(
        default=None,
        description="Optional severity floor for the rule to apply.",
    )
    requires_simulation: bool = Field(
        default=False,
        description="When true, matching remediations must simulate first.",
    )
    requires_approval: bool = Field(
        default=False,
        description="When true, matching remediations require an approver.",
    )
    priority: int = Field(
        default=100,
        ge=0,
        le=10000,
        description="Lower numbers evaluate first.",
    )

    @field_validator("conditions")
    @classmethod
    def limit_conditions(cls, value: List[PolicyCondition]) -> List[PolicyCondition]:
        """Bound rule complexity."""

        if len(value) > 32:
            raise ValueError("a rule may contain at most 32 conditions")
        return value


class PolicyObject(TimestampedModel):
    """
    Versioned security policy governing decisions and remediations.

    Policy engines evaluate ``rules`` against ``SecurityFindingObject`` and
    related context; adapters must never bypass policy with raw scanner data.
    """

    id: UUID = Field(default_factory=new_id, description="Canonical policy id.")
    tenant_id: Optional[UUID] = Field(
        default=None,
        description="Tenant scope; null means platform-global when scope allows.",
    )
    name: str = Field(..., min_length=1, max_length=256, description="Policy name.")
    description: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Human-readable policy purpose.",
    )
    version: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Policy document version (referenced by DecisionObject.policy_version).",
    )
    scope: PolicyScope = Field(..., description="Applicability scope.")
    enabled: bool = Field(default=True, description="Whether the policy is active.")
    rules: List[PolicyRule] = Field(
        ...,
        min_length=1,
        description="Ordered rules; lower priority values win on conflict.",
    )
    effective_from: datetime = Field(
        default_factory=utc_now,
        description="UTC time from which the policy is effective.",
    )
    effective_until: Optional[datetime] = Field(
        default=None,
        description="Optional UTC expiry for the policy.",
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Small string metadata for policy ops (owner team, change ticket).",
    )

    @field_validator("effective_from", "effective_until", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware datetimes."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @field_validator("rules")
    @classmethod
    def unique_rule_ids(cls, value: List[PolicyRule]) -> List[PolicyRule]:
        """Enforce unique rule identifiers within a policy."""

        ids = [rule.rule_id for rule in value]
        if len(ids) != len(set(ids)):
            raise ValueError("policy rule_id values must be unique")
        if len(value) > 256:
            raise ValueError("a policy may contain at most 256 rules")
        return value

    @field_validator("metadata")
    @classmethod
    def limit_metadata(cls, value: Dict[str, str]) -> Dict[str, str]:
        """Cap metadata size."""

        if len(value) > 32:
            raise ValueError("policy metadata limited to 32 entries")
        return value

    @model_validator(mode="after")
    def validate_effectiveness_window(self) -> PolicyObject:
        """Ensure effective_until is after effective_from when set."""

        if (
            self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effective_until must be after effective_from")
        if self.scope == PolicyScope.TENANT and self.tenant_id is None:
            raise ValueError("TENANT-scoped policies require tenant_id")
        if self.scope == PolicyScope.GLOBAL and self.tenant_id is not None:
            raise ValueError("GLOBAL policies must not set tenant_id")
        return self

    def is_effective_at(self, moment: datetime) -> bool:
        """Return whether the policy is enabled and within its time window."""

        if not self.enabled:
            return False
        if moment.tzinfo is None:
            raise ValueError("moment must be timezone-aware")
        if moment < self.effective_from:
            return False
        if self.effective_until is not None and moment >= self.effective_until:
            return False
        return True
