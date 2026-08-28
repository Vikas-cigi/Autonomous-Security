"""Domain enums for the Enterprise Remediation Planner."""

from __future__ import annotations

from enum import Enum


class ExecutionType(str, Enum):
    """Deterministic remediation execution categories."""

    PATCH = "patch"
    CONFIGURATION_CHANGE = "configuration_change"
    SECRET_ROTATION = "secret_rotation"
    FIREWALL_UPDATE = "firewall_update"
    IAM_POLICY_CHANGE = "iam_policy_change"
    NETWORK_ISOLATION = "network_isolation"
    CONTAINER_UPDATE = "container_update"
    PACKAGE_UPGRADE = "package_upgrade"
    MANUAL_INVESTIGATION = "manual_investigation"


class PlanStatus(str, Enum):
    """Lifecycle of a planned (not yet executed) remediation."""

    DRAFT = "draft"
    READY_FOR_SIMULATION = "ready_for_simulation"
    AWAITING_APPROVAL = "awaiting_approval"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class StepKind(str, Enum):
    """Role of a step inside the plan."""

    PREREQUISITE = "prerequisite"
    MITIGATION = "mitigation"
    REMEDIATION = "remediation"
    VALIDATION = "validation"
    ROLLBACK = "rollback"
    NOTIFY = "notify"


class DependencyType(str, Enum):
    """Edge type in the remediation dependency graph."""

    REQUIRES = "requires"
    BLOCKS = "blocks"
    RELATED = "related"


class ImpactBlastRadius(str, Enum):
    """Estimated blast radius of executing the plan."""

    NONE = "none"
    ASSET = "asset"
    GROUP = "group"
    ENVIRONMENT = "environment"
    TENANT = "tenant"


class CostBand(str, Enum):
    """Coarse cost band for planning (not billing)."""

    NEGLIGIBLE = "negligible"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class AuditAction(str, Enum):
    """Audit actions for Remediation Planner operations."""

    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    PLAN_GENERATED = "plan_generated"
    HISTORY_RECORDED = "history_recorded"
    SEARCHED = "searched"
    CANCELLED = "cancelled"
