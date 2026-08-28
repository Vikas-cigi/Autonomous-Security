"""Dependency injection container for Enterprise Approval Engine."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from approval_engine.persistence.approval_audit_repository import (
    PostgresApprovalAuditRepository,
)
from approval_engine.persistence.approval_policy_repository import (
    PostgresApprovalPolicyRepository,
)
from approval_engine.persistence.approval_repository import PostgresApprovalRepository
from approval_engine.persistence.approval_workflow_repository import (
    PostgresApprovalWorkflowRepository,
)
from approval_engine.persistence.session import SessionFactory
from approval_engine.services.approval_audit import ApprovalAuditService
from approval_engine.services.approval_engine_service import ApprovalEngineService
from approval_engine.services.approval_policy import ApprovalPolicyService
from approval_engine.services.approval_routing import ApprovalRoutingService
from approval_engine.services.approval_validation import ApprovalValidationService
from approval_engine.services.approval_workflow import ApprovalWorkflowService
from approval_engine.services.audit_logger import AuditLogger
from approval_engine.services.notification_preparation import (
    NotificationPreparationService,
)


@dataclass
class ApprovalEngineContainer:
    """
    Composition root for Approval Engine.

    Example::

        container = ApprovalEngineContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            approval = svc.engine.submit(request)
    """

    session_factory: SessionFactory

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> ApprovalEngineContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            )
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "ApprovalEngineServices":
        audit_logger = AuditLogger(session)
        approval_repo = PostgresApprovalRepository(session, audit_logger=audit_logger)
        policy_repo = PostgresApprovalPolicyRepository(session)
        workflow_repo = PostgresApprovalWorkflowRepository(session)
        audit_repo = PostgresApprovalAuditRepository(
            session, audit_logger=audit_logger
        )

        routing = ApprovalRoutingService()
        policy = ApprovalPolicyService(policy_repo)
        workflow = ApprovalWorkflowService(routing=routing)
        validation = ApprovalValidationService()
        audit = ApprovalAuditService(audit_repo)
        notifications = NotificationPreparationService()

        engine = ApprovalEngineService(
            approval_repo,
            policy_service=policy,
            workflow_service=workflow,
            routing_service=routing,
            validation_service=validation,
            audit_service=audit,
            notification_service=notifications,
            audit_logger=audit_logger,
        )
        return ApprovalEngineServices(
            audit_logger=audit_logger,
            engine=engine,
            policy=policy,
            workflow=workflow,
            routing=routing,
            validation=validation,
            audit=audit,
            notifications=notifications,
            approval_repository=approval_repo,
            policy_repository=policy_repo,
            workflow_repository=workflow_repo,
            audit_repository=audit_repo,
        )


@dataclass
class ApprovalEngineServices:
    """Bundled services sharing one unit-of-work session."""

    audit_logger: AuditLogger
    engine: ApprovalEngineService
    policy: ApprovalPolicyService
    workflow: ApprovalWorkflowService
    routing: ApprovalRoutingService
    validation: ApprovalValidationService
    audit: ApprovalAuditService
    notifications: NotificationPreparationService
    approval_repository: PostgresApprovalRepository
    policy_repository: PostgresApprovalPolicyRepository
    workflow_repository: PostgresApprovalWorkflowRepository
    audit_repository: PostgresApprovalAuditRepository
