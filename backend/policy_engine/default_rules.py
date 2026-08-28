"""
Default fail-closed local policy rules for Forti-ai.
"""

from __future__ import annotations

from typing import List

from models.enums import ActionClass, PolicyScope, PolicyVerdict, Severity
from policy_engine.models import PolicyRuleSpec


def default_policy_rules() -> List[PolicyRuleSpec]:
    """
    Built-in enterprise baseline.

    Principles:
        - READ / SUGGEST / PLAN are broadly allowed.
        - SIMULATE is allowed with simulation flag.
        - EXECUTE_LOW allowed for operators on low/medium findings only.
        - EXECUTE_LOW on high/critical findings escalates.
        - EXECUTE_HIGH escalates for privileged roles; otherwise denied.
        - Unmatched actions are denied by the engine (never execute without policy).
    """

    return [
        PolicyRuleSpec(
            name="allow-read",
            description="Allow read of canonical security objects.",
            verdict=PolicyVerdict.ALLOW,
            action_classes=[ActionClass.READ],
            scopes=[PolicyScope.GLOBAL, PolicyScope.TENANT, PolicyScope.ASSET],
            priority=10,
        ),
        PolicyRuleSpec(
            name="allow-suggest",
            description="Allow non-mutating remediation suggestions.",
            verdict=PolicyVerdict.ALLOW,
            action_classes=[ActionClass.SUGGEST],
            scopes=[PolicyScope.GLOBAL, PolicyScope.TENANT, PolicyScope.ASSET],
            priority=20,
        ),
        PolicyRuleSpec(
            name="allow-plan",
            description="Allow remediation plan generation without execution.",
            verdict=PolicyVerdict.ALLOW,
            action_classes=[ActionClass.PLAN],
            scopes=[PolicyScope.GLOBAL, PolicyScope.TENANT, PolicyScope.ASSET],
            priority=20,
        ),
        PolicyRuleSpec(
            name="allow-simulate",
            description="Allow dry-run simulation of remediation plans.",
            verdict=PolicyVerdict.ALLOW,
            action_classes=[ActionClass.SIMULATE],
            scopes=[PolicyScope.GLOBAL, PolicyScope.TENANT, PolicyScope.ASSET],
            requires_simulation=True,
            priority=30,
        ),
        PolicyRuleSpec(
            name="escalate-execute-low-high-severity",
            description="Escalate low-class execution when finding severity is high/critical.",
            verdict=PolicyVerdict.ESCALATE,
            action_classes=[ActionClass.EXECUTE_LOW],
            scopes=[PolicyScope.TENANT, PolicyScope.ASSET],
            min_severity=Severity.HIGH,
            requires_approval=True,
            requires_simulation=True,
            priority=35,
        ),
        PolicyRuleSpec(
            name="allow-execute-low",
            description="Allow low-risk execution for operators on low/medium findings.",
            verdict=PolicyVerdict.ALLOW,
            action_classes=[ActionClass.EXECUTE_LOW],
            scopes=[PolicyScope.TENANT, PolicyScope.ASSET],
            required_roles=["operator", "remediator", "admin", "secops"],
            max_severity=Severity.MEDIUM,
            requires_simulation=True,
            priority=40,
        ),
        PolicyRuleSpec(
            name="escalate-execute-high-privileged",
            description="High-impact execution escalates for privileged roles.",
            verdict=PolicyVerdict.ESCALATE,
            action_classes=[ActionClass.EXECUTE_HIGH],
            scopes=[PolicyScope.TENANT, PolicyScope.ASSET, PolicyScope.ENVIRONMENT],
            required_roles=["admin", "secops", "ciso"],
            requires_approval=True,
            requires_simulation=True,
            priority=10,
        ),
        PolicyRuleSpec(
            name="deny-execute-high-unprivileged",
            description="Deny high-impact execution for callers without privileged roles.",
            verdict=PolicyVerdict.DENY,
            action_classes=[ActionClass.EXECUTE_HIGH],
            scopes=[PolicyScope.TENANT, PolicyScope.ASSET, PolicyScope.ENVIRONMENT],
            priority=90,
        ),
    ]
