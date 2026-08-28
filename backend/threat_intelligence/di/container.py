"""Dependency injection container for Threat Intelligence."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from threat_intelligence.persistence.ioc_repository import PostgresIOCRepository
from threat_intelligence.persistence.session import SessionFactory
from threat_intelligence.persistence.threat_feed_repository import (
    PostgresThreatFeedRepository,
)
from threat_intelligence.persistence.threat_intel_repository import (
    PostgresThreatIntelRepository,
)
from threat_intelligence.providers.base import ThreatFeedProviderRegistry
from threat_intelligence.providers.placeholders import default_placeholder_providers
from threat_intelligence.services.audit import AuditLogger
from threat_intelligence.services.cve_enrichment import CVEEnrichmentService
from threat_intelligence.services.exploit_analysis import ExploitAnalysisService
from threat_intelligence.services.ioc_correlation import IOCCorrelationService
from threat_intelligence.services.mitre_mapping import MITREMappingService
from threat_intelligence.services.threat_feed_sync import ThreatFeedSyncService
from threat_intelligence.services.threat_intelligence_service import (
    ThreatIntelligenceService,
)


@dataclass
class ThreatIntelligenceContainer:
    """
    Composition root for threat intelligence repositories and services.

    Example::

        container = ThreatIntelligenceContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            svc.intelligence.enrich_finding(...)
    """

    session_factory: SessionFactory
    provider_registry: ThreatFeedProviderRegistry

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
        provider_registry: ThreatFeedProviderRegistry | None = None,
    ) -> ThreatIntelligenceContainer:
        registry = provider_registry or ThreatFeedProviderRegistry()
        if provider_registry is None:
            for provider in default_placeholder_providers():
                registry.register(provider)
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            ),
            provider_registry=registry,
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "ThreatIntelligenceServices":
        audit = AuditLogger(session)
        intel_repo = PostgresThreatIntelRepository(session, audit_logger=audit)
        ioc_repo = PostgresIOCRepository(session, audit_logger=audit)
        feed_repo = PostgresThreatFeedRepository(session)

        cve = CVEEnrichmentService(intel_repo)
        mitre = MITREMappingService(intel_repo)
        exploit = ExploitAnalysisService(intel_repo)
        ioc_corr = IOCCorrelationService(ioc_repo, intel_repository=intel_repo)
        feed_sync = ThreatFeedSyncService(
            feed_repo,
            self.provider_registry,
            intel_repository=intel_repo,
            ioc_repository=ioc_repo,
            audit_logger=audit,
        )
        intelligence = ThreatIntelligenceService(
            intel_repo,
            cve_enrichment=cve,
            mitre_mapping=mitre,
            exploit_analysis=exploit,
            ioc_correlation=ioc_corr,
            audit_logger=audit,
        )
        return ThreatIntelligenceServices(
            audit=audit,
            intelligence=intelligence,
            cve_enrichment=cve,
            mitre_mapping=mitre,
            exploit_analysis=exploit,
            ioc_correlation=ioc_corr,
            feed_sync=feed_sync,
            intel_repository=intel_repo,
            ioc_repository=ioc_repo,
            feed_repository=feed_repo,
            provider_registry=self.provider_registry,
        )


@dataclass
class ThreatIntelligenceServices:
    """Bundled services sharing one unit-of-work session."""

    audit: AuditLogger
    intelligence: ThreatIntelligenceService
    cve_enrichment: CVEEnrichmentService
    mitre_mapping: MITREMappingService
    exploit_analysis: ExploitAnalysisService
    ioc_correlation: IOCCorrelationService
    feed_sync: ThreatFeedSyncService
    intel_repository: PostgresThreatIntelRepository
    ioc_repository: PostgresIOCRepository
    feed_repository: PostgresThreatFeedRepository
    provider_registry: ThreatFeedProviderRegistry
