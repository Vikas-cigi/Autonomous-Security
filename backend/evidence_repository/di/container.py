"""Dependency injection container for the Evidence Repository."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from evidence_repository.interfaces.repository import EvidenceRepository
from evidence_repository.persistence.postgres_repository import PostgresEvidenceRepository
from evidence_repository.persistence.session import SessionFactory
from evidence_repository.services.audit import AuditLogger
from evidence_repository.services.correlation import CorrelationService
from evidence_repository.services.deduplication import DeduplicationService
from evidence_repository.services.search import SearchService


@dataclass
class EvidenceRepositoryContainer:
    """
    Composition root for repository + domain services.

    Example::

        container = EvidenceRepositoryContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            services = container.build(session)
            services.deduplication.ingest(finding)
    """

    session_factory: SessionFactory

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> EvidenceRepositoryContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            )
        )

    def session(self):
        """Yield a transactional session from the factory."""

        return self.session_factory.session()

    def build(self, session: Session) -> "EvidenceRepositoryServices":
        """Wire repository and services against an active session."""

        audit = AuditLogger(session)
        repository: EvidenceRepository = PostgresEvidenceRepository(
            session, audit_logger=audit
        )
        return EvidenceRepositoryServices(
            repository=repository,
            audit=audit,
            deduplication=DeduplicationService(repository),
            correlation=CorrelationService(repository),
            search=SearchService(repository),
        )


@dataclass
class EvidenceRepositoryServices:
    """Bundled services sharing one unit-of-work session."""

    repository: EvidenceRepository
    audit: AuditLogger
    deduplication: DeduplicationService
    correlation: CorrelationService
    search: SearchService
