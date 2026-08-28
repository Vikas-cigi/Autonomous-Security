"""
Enterprise Execution Engine.

Orchestrates approved remediation plan execution after Approval Engine and
before Verification Engine.

Never evaluates policy, recalculates trust/risk, invokes AI, or modifies plans.
"""

from execution_engine.di.container import (
    ExecutionEngineContainer,
    ExecutionEngineServices,
)
from execution_engine.domain.enums import ExecutionStatus, RollbackStatus
from execution_engine.domain.history import ExecutionAuditRecord, ExecutionHistory
from execution_engine.domain.inputs import ExecutionRequest
from execution_engine.domain.models import (
    ExecutionResult,
    ExecutionStep,
    RollbackPlan,
    StepExecutionResult,
    VerificationRequest,
)
from execution_engine.interfaces.execution_audit_repository import (
    ExecutionAuditRepository,
)
from execution_engine.interfaces.execution_history_repository import (
    ExecutionHistoryRepository,
)
from execution_engine.interfaces.execution_repository import ExecutionRepository
from execution_engine.interfaces.rollback_repository import RollbackRepository
from execution_engine.services.execution_engine_service import ExecutionEngineService

__all__ = [
    "ExecutionAuditRecord",
    "ExecutionAuditRepository",
    "ExecutionEngineContainer",
    "ExecutionEngineService",
    "ExecutionEngineServices",
    "ExecutionHistory",
    "ExecutionHistoryRepository",
    "ExecutionRepository",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionStatus",
    "ExecutionStep",
    "RollbackPlan",
    "RollbackRepository",
    "RollbackStatus",
    "StepExecutionResult",
    "VerificationRequest",
]

__version__ = "1.0.0"
