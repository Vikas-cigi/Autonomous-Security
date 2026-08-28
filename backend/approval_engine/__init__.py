"""
Enterprise Approval Engine.

Governs remediation execution authorization after simulation and before
execution. Never executes remediation, never calls AI, never mutates plans
or risk calculations.

Pipeline position: after Simulation Engine, before Execution Engine.
"""

from approval_engine.di.container import (
    ApprovalEngineContainer,
    ApprovalEngineServices,
)
from approval_engine.domain.enums import ApprovalState, ApprovalType
from approval_engine.domain.history import ApprovalAuditRecord, ApprovalHistory
from approval_engine.domain.inputs import ApprovalSubmitRequest
from approval_engine.domain.models import (
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalRule,
    ApprovalWorkflow,
    ExecutionAuthorization,
)
from approval_engine.interfaces.approval_audit_repository import (
    ApprovalAuditRepository,
)
from approval_engine.interfaces.approval_policy_repository import (
    ApprovalPolicyRepository,
)
from approval_engine.interfaces.approval_repository import ApprovalRepository
from approval_engine.interfaces.approval_workflow_repository import (
    ApprovalWorkflowRepository,
)
from approval_engine.services.approval_engine_service import ApprovalEngineService

__all__ = [
    "ApprovalAuditRecord",
    "ApprovalAuditRepository",
    "ApprovalDecision",
    "ApprovalEngineContainer",
    "ApprovalEngineService",
    "ApprovalEngineServices",
    "ApprovalHistory",
    "ApprovalPolicy",
    "ApprovalPolicyRepository",
    "ApprovalRepository",
    "ApprovalRequest",
    "ApprovalRule",
    "ApprovalState",
    "ApprovalSubmitRequest",
    "ApprovalType",
    "ApprovalWorkflow",
    "ApprovalWorkflowRepository",
    "ExecutionAuthorization",
]

__version__ = "1.0.0"
