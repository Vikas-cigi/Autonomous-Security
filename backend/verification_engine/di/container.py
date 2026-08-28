"""Dependency injection container for Enterprise Verification Engine."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from verification_engine.persistence.session import SessionFactory
from verification_engine.persistence.verification_audit_repository import (
    PostgresVerificationAuditRepository,
)
from verification_engine.persistence.verification_evidence_repository import (
    PostgresVerificationEvidenceRepository,
)
from verification_engine.persistence.verification_history_repository import (
    PostgresVerificationHistoryRepository,
)
from verification_engine.persistence.verification_repository import (
    PostgresVerificationRepository,
)
from verification_engine.services.audit_logger import AuditLogger
from verification_engine.services.verification_audit import VerificationAuditService
from verification_engine.services.verification_check_runner import VerificationCheckRunner
from verification_engine.services.verification_comparison import (
    VerificationComparisonService,
)
from verification_engine.services.verification_engine_service import (
    VerificationEngineService,
)
from verification_engine.services.verification_evidence import VerificationEvidenceService
from verification_engine.services.verification_history_service import (
    VerificationHistoryService,
)
from verification_engine.services.verification_reporting import (
    VerificationReportingService,
)
from verification_engine.services.verification_validation import (
    VerificationValidationService,
)
from verification_engine.services.verification_workflow import VerificationWorkflowService


@dataclass
class VerificationEngineContainer:
    """
    Composition root for Verification Engine.

    Example::

        container = VerificationEngineContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            result = svc.engine.verify(request)
    """

    session_factory: SessionFactory

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> VerificationEngineContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            )
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "VerificationEngineServices":
        audit_logger = AuditLogger(session)
        verification_repo = PostgresVerificationRepository(
            session, audit_logger=audit_logger
        )
        history_repo = PostgresVerificationHistoryRepository(session)
        audit_repo = PostgresVerificationAuditRepository(
            session, audit_logger=audit_logger
        )
        evidence_repo = PostgresVerificationEvidenceRepository(session)

        validation = VerificationValidationService()
        workflow = VerificationWorkflowService()
        comparison = VerificationComparisonService()
        evidence = VerificationEvidenceService(evidence_repo)
        checks = VerificationCheckRunner()
        reporting = VerificationReportingService()
        audit = VerificationAuditService(audit_repo)
        history = VerificationHistoryService(verification_repo, history_repo)

        engine = VerificationEngineService(
            verification_repo,
            evidence_repository=evidence_repo,
            validation=validation,
            workflow=workflow,
            comparison=comparison,
            evidence=evidence,
            checks=checks,
            reporting=reporting,
            audit=audit,
            history=history,
        )
        return VerificationEngineServices(
            audit_logger=audit_logger,
            engine=engine,
            validation=validation,
            workflow=workflow,
            comparison=comparison,
            evidence=evidence,
            checks=checks,
            reporting=reporting,
            audit=audit,
            history=history,
            verification_repository=verification_repo,
            history_repository=history_repo,
            audit_repository=audit_repo,
            evidence_repository=evidence_repo,
        )


@dataclass
class VerificationEngineServices:
    """Bundled services sharing one unit-of-work session."""

    audit_logger: AuditLogger
    engine: VerificationEngineService
    validation: VerificationValidationService
    workflow: VerificationWorkflowService
    comparison: VerificationComparisonService
    evidence: VerificationEvidenceService
    checks: VerificationCheckRunner
    reporting: VerificationReportingService
    audit: VerificationAuditService
    history: VerificationHistoryService
    verification_repository: PostgresVerificationRepository
    history_repository: PostgresVerificationHistoryRepository
    audit_repository: PostgresVerificationAuditRepository
    evidence_repository: PostgresVerificationEvidenceRepository
