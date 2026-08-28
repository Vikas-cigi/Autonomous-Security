"""Dependency injection container for Enterprise Execution Engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from execution_engine.adapters.deterministic import DeterministicRecordingAdapter
from execution_engine.interfaces.step_adapter import StepInfrastructureAdapter
from execution_engine.persistence.execution_audit_repository import (
    PostgresExecutionAuditRepository,
)
from execution_engine.persistence.execution_history_repository import (
    PostgresExecutionHistoryRepository,
)
from execution_engine.persistence.execution_repository import PostgresExecutionRepository
from execution_engine.persistence.rollback_repository import PostgresRollbackRepository
from execution_engine.persistence.session import SessionFactory
from execution_engine.services.audit_logger import AuditLogger
from execution_engine.services.execution_audit import ExecutionAuditService
from execution_engine.services.execution_coordinator import ExecutionCoordinator
from execution_engine.services.execution_engine_service import ExecutionEngineService
from execution_engine.services.execution_history import ExecutionHistoryService
from execution_engine.services.execution_monitoring import ExecutionMonitoringService
from execution_engine.services.execution_step_executor import ExecutionStepExecutor
from execution_engine.services.execution_validation import ExecutionValidationService
from execution_engine.services.execution_workflow import ExecutionWorkflowService
from execution_engine.services.rollback_service import RollbackService


@dataclass
class ExecutionEngineContainer:
    """
    Composition root for Execution Engine.

    Example::

        container = ExecutionEngineContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            result = svc.engine.execute(request)
    """

    session_factory: SessionFactory
    step_adapter: Optional[StepInfrastructureAdapter] = None

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
        step_adapter: Optional[StepInfrastructureAdapter] = None,
    ) -> ExecutionEngineContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            ),
            step_adapter=step_adapter,
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "ExecutionEngineServices":
        audit_logger = AuditLogger(session)
        exec_repo = PostgresExecutionRepository(session, audit_logger=audit_logger)
        history_repo = PostgresExecutionHistoryRepository(session)
        audit_repo = PostgresExecutionAuditRepository(
            session, audit_logger=audit_logger
        )
        rollback_repo = PostgresRollbackRepository(session)

        adapter = self.step_adapter or DeterministicRecordingAdapter()
        monitoring = ExecutionMonitoringService()
        validation = ExecutionValidationService()
        workflow = ExecutionWorkflowService()
        step_executor = ExecutionStepExecutor(adapter=adapter, monitoring=monitoring)
        rollback = RollbackService(adapter=adapter, monitoring=monitoring)
        coordinator = ExecutionCoordinator(
            workflow=workflow,
            step_executor=step_executor,
            rollback=rollback,
            monitoring=monitoring,
        )
        audit = ExecutionAuditService(audit_repo)
        history = ExecutionHistoryService(exec_repo, history_repo)

        engine = ExecutionEngineService(
            exec_repo,
            rollback_repository=rollback_repo,
            validation=validation,
            workflow=workflow,
            coordinator=coordinator,
            monitoring=monitoring,
            rollback=rollback,
            audit=audit,
            history=history,
            step_executor=step_executor,
        )
        return ExecutionEngineServices(
            audit_logger=audit_logger,
            engine=engine,
            validation=validation,
            workflow=workflow,
            coordinator=coordinator,
            step_executor=step_executor,
            rollback=rollback,
            monitoring=monitoring,
            audit=audit,
            history=history,
            execution_repository=exec_repo,
            history_repository=history_repo,
            audit_repository=audit_repo,
            rollback_repository=rollback_repo,
            step_adapter=adapter,
        )


@dataclass
class ExecutionEngineServices:
    """Bundled services sharing one unit-of-work session."""

    audit_logger: AuditLogger
    engine: ExecutionEngineService
    validation: ExecutionValidationService
    workflow: ExecutionWorkflowService
    coordinator: ExecutionCoordinator
    step_executor: ExecutionStepExecutor
    rollback: RollbackService
    monitoring: ExecutionMonitoringService
    audit: ExecutionAuditService
    history: ExecutionHistoryService
    execution_repository: PostgresExecutionRepository
    history_repository: PostgresExecutionHistoryRepository
    audit_repository: PostgresExecutionAuditRepository
    rollback_repository: PostgresRollbackRepository
    step_adapter: StepInfrastructureAdapter
