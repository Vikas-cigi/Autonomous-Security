"""
Policy Engine request / decision models.

These are business-logic contracts for authorization of security actions.
They are independent of LLM providers and UI frameworks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import ActorReference, FortiBaseModel, new_id, utc_now
from models.enums import ActionClass, PolicyScope, PolicyVerdict, Severity
from models.security_finding import SecurityFindingObject


class ResourceRef(FortiBaseModel):
    """Resource an action targets (asset, finding, playbook, etc.)."""

    resource_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Resource class: asset | finding | remediation | playbook | tenant.",
    )
    resource_id: UUID = Field(..., description="Target resource identifier.")
    environment: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional environment label: prod | staging | dev.",
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional resource labels for rule matching.",
    )

    @field_validator("resource_type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        """Normalize resource type to lowercase token."""

        return value.strip().lower()

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: Optional[str]) -> Optional[str]:
        """Normalize environment labels."""

        if value is None:
            return value
        return value.strip().lower()

    @field_validator("labels")
    @classmethod
    def limit_labels(cls, value: Dict[str, str]) -> Dict[str, str]:
        """Cap label map size."""

        if len(value) > 32:
            raise ValueError("resource labels limited to 32 entries")
        return value


class PolicyInput(FortiBaseModel):
    """
    Canonical inputs required to evaluate a security action.

    Every execution path must construct this object before acting.
    """

    tenant_id: UUID = Field(..., description="Tenant under which the action is requested.")
    user: ActorReference = Field(..., description="Acting user or service principal.")
    scope: PolicyScope = Field(
        ...,
        description="Policy scope context for the evaluation.",
    )
    action_class: ActionClass = Field(
        ...,
        description="Requested action capability class.",
    )
    resource: ResourceRef = Field(..., description="Target resource reference.")
    finding: Optional[SecurityFindingObject] = Field(
        default=None,
        description="Optional canonical finding associated with the action.",
    )
    roles: List[str] = Field(
        default_factory=list,
        description="Caller roles used for RBAC-style rule predicates.",
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional ABAC attributes (never raw scanner payloads).",
    )

    @field_validator("roles")
    @classmethod
    def normalize_roles(cls, value: List[str]) -> List[str]:
        """Normalize and bound roles."""

        normalized = sorted({item.strip().lower() for item in value if item.strip()})
        if len(normalized) > 64:
            raise ValueError("roles limited to 64 entries")
        return normalized

    @model_validator(mode="after")
    def finding_tenant_alignment(self) -> PolicyInput:
        """When a finding is supplied, it must belong to the same tenant."""

        if self.finding is not None and self.finding.tenant_id != self.tenant_id:
            raise ValueError("finding.tenant_id must match policy input tenant_id")
        return self


class PolicyRuleSpec(FortiBaseModel):
    """
    Local (non-OPA) rule specification evaluated by ``PolicyEvaluator``.

    Designed so an OPA/Rego backend can express equivalent predicates later.
    """

    rule_id: UUID = Field(default_factory=new_id, description="Stable rule id.")
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=2000)
    verdict: PolicyVerdict = Field(
        ...,
        description="Verdict emitted when this rule matches.",
    )
    action_classes: List[ActionClass] = Field(
        ...,
        min_length=1,
        description="Action classes this rule applies to.",
    )
    scopes: List[PolicyScope] = Field(
        default_factory=lambda: [PolicyScope.GLOBAL, PolicyScope.TENANT],
        description="Scopes this rule may apply within.",
    )
    environments: List[str] = Field(
        default_factory=list,
        description="If non-empty, resource.environment must be in this list.",
    )
    required_roles: List[str] = Field(
        default_factory=list,
        description="If non-empty, caller must hold at least one role.",
    )
    max_severity: Optional[Severity] = Field(
        default=None,
        description="If set with a finding, finding.severity must be <= this level.",
    )
    min_severity: Optional[Severity] = Field(
        default=None,
        description="If set with a finding, finding.severity must be >= this level.",
    )
    resource_types: List[str] = Field(
        default_factory=list,
        description="If non-empty, resource.resource_type must be listed.",
    )
    priority: int = Field(
        default=100,
        ge=0,
        le=10000,
        description="Lower numbers win on first-match evaluation.",
    )
    requires_approval: bool = Field(default=False)
    requires_simulation: bool = Field(default=False)
    enabled: bool = Field(default=True)
    policy_version: str = Field(
        default="forti-local-1.0.0",
        min_length=1,
        max_length=64,
    )

    @field_validator("environments", "required_roles", "resource_types")
    @classmethod
    def normalize_string_lists(cls, value: List[str]) -> List[str]:
        """Lowercase and deduplicate string list fields."""

        return sorted({item.strip().lower() for item in value if item.strip()})


class PolicyDecision(FortiBaseModel):
    """
    Authoritative policy decision for a requested security action.

    Downstream execution MUST honor this object. ``ALLOW`` is the only verdict
    that authorizes immediate execution. ``ESCALATE`` requires approval.
    ``DENY`` forbids the action.
    """

    decision_id: UUID = Field(default_factory=new_id)
    verdict: PolicyVerdict = Field(..., description="ALLOW | DENY | ESCALATE.")
    reason: str = Field(..., min_length=1, max_length=4000)
    action_class: ActionClass
    tenant_id: UUID
    resource_id: UUID
    matched_rule_ids: List[UUID] = Field(default_factory=list)
    policy_version: str = Field(..., min_length=1, max_length=64)
    requires_approval: bool = Field(default=False)
    requires_simulation: bool = Field(default=False)
    evaluator: str = Field(
        default="local",
        description="Backend that produced the decision: local | opa.",
    )
    evaluated_at: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware timestamps."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def enforce_execution_semantics(self) -> PolicyDecision:
        """Encode fail-safe semantics on the decision object itself."""

        if self.verdict == PolicyVerdict.ESCALATE and not self.requires_approval:
            raise ValueError("ESCALATE decisions require requires_approval=True")

        if self.verdict == PolicyVerdict.ALLOW and self.action_class in {
            ActionClass.EXECUTE_LOW,
            ActionClass.EXECUTE_HIGH,
        }:
            if not self.matched_rule_ids:
                raise ValueError(
                    "ALLOW for execute actions requires at least one matched rule "
                    "(never execute without policy)"
                )
        return self

    @property
    def allowed(self) -> bool:
        """True only when immediate execution is authorized."""

        return self.verdict == PolicyVerdict.ALLOW

    @property
    def denied(self) -> bool:
        """True when the action is forbidden."""

        return self.verdict == PolicyVerdict.DENY
