"""Built-in default approval policy rules (deterministic catalog)."""

from __future__ import annotations

from approval_engine.domain.enums import (
    ApprovalMode,
    ApprovalType,
    ApproverRole,
    PolicyMatchMode,
)
from approval_engine.domain.models import ApprovalRule


def default_approval_rules() -> list[ApprovalRule]:
    """
    Example organizational policy logic:

    - Critical risk → Security Manager + Infrastructure Manager
    - Production + firewall change → Network Team + Security
    - Low + Development + auto_approve flag → AutoApproved
    """

    return [
        ApprovalRule(
            name="auto_approve_low_dev",
            priority=10,
            match_mode=PolicyMatchMode.ALL,
            risk_levels=["low"],
            environments=["development", "dev"],
            auto_approve=True,
            required_roles=[],
            approval_types=[],
            mode=ApprovalMode.SEQUENTIAL,
            explanation="Low risk in development may auto-approve when enabled.",
        ),
        ApprovalRule(
            name="critical_risk_dual_control",
            priority=20,
            match_mode=PolicyMatchMode.ANY,
            risk_levels=["critical"],
            required_roles=[
                ApproverRole.SECURITY_MANAGER,
                ApproverRole.INFRASTRUCTURE_MANAGER,
            ],
            approval_types=[
                ApprovalType.SECURITY_REVIEW,
                ApprovalType.INFRASTRUCTURE_REVIEW,
            ],
            mode=ApprovalMode.SEQUENTIAL,
            explanation="Critical risk requires security and infrastructure managers.",
        ),
        ApprovalRule(
            name="production_firewall_change",
            priority=30,
            match_mode=PolicyMatchMode.ALL,
            environments=["production", "prod"],
            remediation_types=[
                "firewall_change",
                "network_change",
                "security_group_change",
            ],
            required_roles=[
                ApproverRole.NETWORK_TEAM,
                ApproverRole.SECURITY_APPROVER,
            ],
            approval_types=[
                ApprovalType.INFRASTRUCTURE_REVIEW,
                ApprovalType.SECURITY_REVIEW,
            ],
            mode=ApprovalMode.SEQUENTIAL,
            explanation="Production firewall/network changes need network + security.",
        ),
        ApprovalRule(
            name="compliance_gated",
            priority=40,
            match_mode=PolicyMatchMode.ANY,
            compliance_tags=["pci", "hipaa", "sox", "fedramp"],
            required_roles=[ApproverRole.COMPLIANCE_OFFICER],
            approval_types=[ApprovalType.COMPLIANCE_REVIEW],
            mode=ApprovalMode.SEQUENTIAL,
            explanation="Compliance-tagged assets require compliance officer approval.",
        ),
        ApprovalRule(
            name="production_high_risk",
            priority=50,
            match_mode=PolicyMatchMode.ALL,
            risk_levels=["high", "critical"],
            environments=["production", "prod"],
            required_roles=[
                ApproverRole.SECURITY_APPROVER,
                ApproverRole.CHANGE_MANAGER,
            ],
            approval_types=[
                ApprovalType.SECURITY_REVIEW,
                ApprovalType.OPERATIONS_REVIEW,
            ],
            mode=ApprovalMode.SEQUENTIAL,
            explanation="High/critical production remediations need security + change.",
        ),
        ApprovalRule(
            name="emergency_change",
            priority=5,
            match_mode=PolicyMatchMode.ALL,
            emergency_only=True,
            required_roles=[ApproverRole.EMERGENCY_APPROVER],
            approval_types=[ApprovalType.EMERGENCY_CHANGE],
            mode=ApprovalMode.PARALLEL,
            explanation="Emergency path: single emergency approver, parallel mode.",
        ),
        ApprovalRule(
            name="default_operations",
            priority=900,
            match_mode=PolicyMatchMode.ALL,
            required_roles=[ApproverRole.OPERATIONS_MANAGER],
            approval_types=[ApprovalType.OPERATIONS_REVIEW],
            mode=ApprovalMode.SEQUENTIAL,
            explanation="Default catch-all: operations manager approval.",
        ),
    ]
