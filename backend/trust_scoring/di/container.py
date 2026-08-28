"""Dependency injection container for Trust Scoring."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from trust_scoring.persistence.confidence_repository import PostgresConfidenceRepository
from trust_scoring.persistence.session import SessionFactory
from trust_scoring.persistence.trust_history_repository import (
    PostgresTrustHistoryRepository,
)
from trust_scoring.persistence.trust_repository import PostgresTrustRepository
from trust_scoring.services.audit import AuditLogger
from trust_scoring.services.correlation_confidence import CorrelationConfidenceService
from trust_scoring.services.cross_validation import CrossValidationService
from trust_scoring.services.evidence_confidence import EvidenceConfidenceService
from trust_scoring.services.historical_trust import HistoricalTrustService
from trust_scoring.services.trust_aggregation import TrustAggregationService
from trust_scoring.services.trust_scoring_service import TrustScoringService


@dataclass
class TrustScoringContainer:
    """
    Composition root for Trust Scoring repositories and services.

    Example::

        container = TrustScoringContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            assessment = svc.scoring.score(scoring_input)
    """

    session_factory: SessionFactory

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> TrustScoringContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            )
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "TrustScoringServices":
        audit = AuditLogger(session)
        trust_repo = PostgresTrustRepository(session, audit_logger=audit)
        confidence_repo = PostgresConfidenceRepository(session, audit_logger=audit)
        history_repo = PostgresTrustHistoryRepository(session, audit_logger=audit)

        evidence = EvidenceConfidenceService()
        cross = CrossValidationService()
        historical = HistoricalTrustService()
        correlation = CorrelationConfidenceService()
        aggregation = TrustAggregationService()

        scoring = TrustScoringService(
            trust_repo,
            confidence_repository=confidence_repo,
            history_repository=history_repo,
            evidence_service=evidence,
            cross_validation_service=cross,
            historical_service=historical,
            correlation_service=correlation,
            aggregation_service=aggregation,
            audit_logger=audit,
        )
        return TrustScoringServices(
            audit=audit,
            scoring=scoring,
            evidence_confidence=evidence,
            cross_validation=cross,
            historical_trust=historical,
            correlation_confidence=correlation,
            aggregation=aggregation,
            trust_repository=trust_repo,
            confidence_repository=confidence_repo,
            history_repository=history_repo,
        )


@dataclass
class TrustScoringServices:
    """Bundled services sharing one unit-of-work session."""

    audit: AuditLogger
    scoring: TrustScoringService
    evidence_confidence: EvidenceConfidenceService
    cross_validation: CrossValidationService
    historical_trust: HistoricalTrustService
    correlation_confidence: CorrelationConfidenceService
    aggregation: TrustAggregationService
    trust_repository: PostgresTrustRepository
    confidence_repository: PostgresConfidenceRepository
    history_repository: PostgresTrustHistoryRepository
