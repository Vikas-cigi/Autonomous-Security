"""
Enterprise Remediation Planner.

Converts an approved DecisionObject into a structured, executable
RemediationPlan. Does not execute infrastructure changes. No AI calls.

Pipeline position: after Decision Service, before Simulation Engine.
"""

from remediation_planner.di.container import (
    RemediationPlannerContainer,
    RemediationPlannerServices,
)
from remediation_planner.domain.enums import ExecutionType, PlanStatus
from remediation_planner.domain.history import RemediationAuditRecord, RemediationHistory
from remediation_planner.domain.inputs import RemediationPlanRequest
from remediation_planner.domain.models import (
    ApprovalRequirement,
    ChangeWindow,
    DependencyGraph,
    EstimatedDuration,
    EstimatedImpact,
    ExecutionTask,
    RemediationCost,
    RemediationPlan,
    RemediationStep,
    RollbackPlan,
    ValidationCheck,
)
from remediation_planner.interfaces.remediation_history_repository import (
    RemediationHistoryRepository,
)
from remediation_planner.interfaces.remediation_plan_repository import (
    RemediationPlanRepository,
)
from remediation_planner.services.remediation_planner_service import (
    RemediationPlannerService,
)

__all__ = [
    "ApprovalRequirement",
    "ChangeWindow",
    "DependencyGraph",
    "EstimatedDuration",
    "EstimatedImpact",
    "ExecutionTask",
    "ExecutionType",
    "PlanStatus",
    "RemediationAuditRecord",
    "RemediationCost",
    "RemediationHistory",
    "RemediationHistoryRepository",
    "RemediationPlan",
    "RemediationPlanRepository",
    "RemediationPlanRequest",
    "RemediationPlannerContainer",
    "RemediationPlannerService",
    "RemediationPlannerServices",
    "RemediationStep",
    "RollbackPlan",
    "ValidationCheck",
]

__version__ = "1.0.0"
