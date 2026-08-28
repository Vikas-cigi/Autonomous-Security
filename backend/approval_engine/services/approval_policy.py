"""Policy evaluation for required approvers and auto-approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence
from uuid import UUID

from approval_engine.domain.enums import (
    ApprovalMode,
    ApprovalType,
    ApproverRole,
    PolicyMatchMode,
)
from approval_engine.domain.inputs import ApprovalSubmitRequest
from approval_engine.domain.models import ApprovalPolicy, ApprovalRule
from approval_engine.domain.policy_catalog import default_approval_rules
from approval_engine.interfaces.approval_policy_repository import (
    ApprovalPolicyRepository,
)


@dataclass(frozen=True)
class PolicyEvaluationResult:
    policy_id: Optional[UUID]
    policy_version: str
    matched_rules: List[ApprovalRule]
    required_roles: List[ApproverRole]
    approval_types: List[ApprovalType]
    mode: ApprovalMode
    auto_approve: bool
    explanation: str


class ApprovalPolicyService:
    """
    Evaluate organizational approval policies deterministically.

    Never modifies remediation plans or risk calculations.
    """

    def __init__(
        self,
        policy_repository: Optional[ApprovalPolicyRepository] = None,
    ) -> None:
        self._repo = policy_repository

    def ensure_default_policy(self, tenant_id: UUID) -> ApprovalPolicy:
        if self._repo is None:
            return ApprovalPolicy(
                tenant_id=tenant_id,
                name="default",
                rules=default_approval_rules(),
                description="Built-in default approval policy",
            )
        existing = self._repo.find_default(tenant_id)
        if existing is not None:
            return existing
        policy = ApprovalPolicy(
            tenant_id=tenant_id,
            name="default",
            rules=default_approval_rules(),
            description="Built-in default approval policy",
        )
        return self._repo.save(policy)

    def resolve_policy(
        self,
        request: ApprovalSubmitRequest,
    ) -> ApprovalPolicy:
        tenant_id = request.decision.tenant_id
        if request.policy_id and self._repo is not None:
            return self._repo.get(request.policy_id, tenant_id)
        return self.ensure_default_policy(tenant_id)

    def evaluate(
        self,
        request: ApprovalSubmitRequest,
        *,
        policy: Optional[ApprovalPolicy] = None,
    ) -> PolicyEvaluationResult:
        policy = policy or self.resolve_policy(request)
        rules = [r for r in policy.rules if r.enabled]
        rules = sorted(rules, key=lambda r: r.priority)

        matched: List[ApprovalRule] = []
        for rule in rules:
            if not self._matches(rule, request):
                continue
            # Auto-approve only when org policy explicitly enables it
            if rule.auto_approve:
                if request.org_policy.auto_approve_enabled:
                    return PolicyEvaluationResult(
                        policy_id=policy.id,
                        policy_version=policy.version,
                        matched_rules=[rule],
                        required_roles=[],
                        approval_types=[],
                        mode=ApprovalMode.SEQUENTIAL,
                        auto_approve=True,
                        explanation=rule.explanation or "Auto-approved by policy.",
                    )
                continue
            matched.append(rule)
            if rule.name != "default_operations":
                break

        if not matched:
            # fall through to last default if present
            defaults = [r for r in rules if r.name == "default_operations"]
            matched = defaults[:1] if defaults else []

        roles: List[ApproverRole] = []
        types: List[ApprovalType] = []
        mode = ApprovalMode.SEQUENTIAL
        for rule in matched:
            for role in rule.required_roles:
                if role not in roles:
                    roles.append(role)
            for t in rule.approval_types:
                if t not in types:
                    types.append(t)
            mode = rule.mode

        if not roles and not (
            matched and matched[0].auto_approve and request.org_policy.auto_approve_enabled
        ):
            roles = [ApproverRole.OPERATIONS_MANAGER]
            types = [ApprovalType.OPERATIONS_REVIEW]

        explanation = "; ".join(
            (r.explanation or r.name) for r in matched
        ) or "Default operations approval required."

        return PolicyEvaluationResult(
            policy_id=policy.id,
            policy_version=policy.version,
            matched_rules=matched,
            required_roles=roles,
            approval_types=types,
            mode=mode,
            auto_approve=False,
            explanation=explanation,
        )

    def _matches(self, rule: ApprovalRule, request: ApprovalSubmitRequest) -> bool:
        if rule.emergency_only and not request.emergency:
            return False
        if rule.emergency_only and request.emergency:
            return True

        checks: List[bool] = []

        if rule.risk_levels:
            checks.append(
                request.risk.risk_level.lower() in {x.lower() for x in rule.risk_levels}
            )
        if rule.environments:
            env = (request.asset.environment or "").lower() if request.asset else ""
            checks.append(env in {x.lower() for x in rule.environments})
        if rule.min_asset_criticality is not None:
            crit = request.asset.criticality if request.asset else 0.0
            checks.append(crit >= rule.min_asset_criticality)
        if rule.compliance_tags:
            tags = {
                t.lower()
                for t in (request.asset.compliance_tags if request.asset else [])
            }
            checks.append(
                any(t.lower() in tags for t in rule.compliance_tags)
            )
        if rule.business_units:
            bu = (request.asset.business_unit or "").lower() if request.asset else ""
            checks.append(bu in {x.lower() for x in rule.business_units})
        if rule.remediation_types:
            checks.append(
                request.plan.execution_type.lower()
                in {x.lower() for x in rule.remediation_types}
            )
        if rule.require_change_window is not None:
            checks.append(
                request.plan.change_window_required == rule.require_change_window
            )

        # Auto-approve rule also needs risk/env match already in checks
        if rule.auto_approve and not checks:
            return False

        if not checks:
            # catch-all rules with no predicates
            return rule.name == "default_operations" or (
                not rule.emergency_only and not rule.auto_approve and bool(rule.required_roles)
                and not any(
                    [
                        rule.risk_levels,
                        rule.environments,
                        rule.compliance_tags,
                        rule.business_units,
                        rule.remediation_types,
                        rule.min_asset_criticality is not None,
                    ]
                )
            )

        if rule.match_mode == PolicyMatchMode.ANY:
            return any(checks)
        return all(checks)

    def save_policy(self, policy: ApprovalPolicy) -> ApprovalPolicy:
        if self._repo is None:
            return policy
        return self._repo.save(policy)

    def list_policies(self, tenant_id: UUID) -> Sequence[ApprovalPolicy]:
        if self._repo is None:
            return [self.ensure_default_policy(tenant_id)]
        return self._repo.list_for_tenant(tenant_id)
