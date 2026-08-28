"""Facade service for finding enrichment workflows."""

from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID

from models.common import utc_now
from threat_intelligence.domain.enums import AuditAction
from threat_intelligence.domain.models import (
    Campaign,
    MalwareFamily,
    ThreatActor,
    ThreatIntelligence,
)
from threat_intelligence.interfaces.threat_intel_repository import ThreatIntelRepository
from threat_intelligence.query.filters import ThreatIntelSearchFilter
from threat_intelligence.query.pagination import Page, PageRequest
from threat_intelligence.services.audit import AuditLogger
from threat_intelligence.services.cve_enrichment import CVEEnrichmentService
from threat_intelligence.services.exploit_analysis import ExploitAnalysisService
from threat_intelligence.services.ioc_correlation import IOCCorrelationService
from threat_intelligence.services.mitre_mapping import MITREMappingService


class ThreatIntelligenceService:
    """
    Application facade between Evidence Repository findings and Risk Engine.

    Orchestrates CVE, MITRE, exploit, and IOC enrichment without modifying
    ``SecurityFindingObject`` (join by ``finding_id``).
    """

    def __init__(
        self,
        repository: ThreatIntelRepository,
        *,
        cve_enrichment: CVEEnrichmentService,
        mitre_mapping: MITREMappingService,
        exploit_analysis: ExploitAnalysisService,
        ioc_correlation: Optional[IOCCorrelationService] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._repo = repository
        self._cve = cve_enrichment
        self._mitre = mitre_mapping
        self._exploit = exploit_analysis
        self._ioc = ioc_correlation
        self._audit = audit_logger

    def get_or_create_for_finding(
        self,
        *,
        tenant_id: UUID,
        finding_id: UUID,
        cve_ids: Optional[Sequence[str]] = None,
        actor: Optional[str] = None,
    ) -> ThreatIntelligence:
        existing = self._repo.find_by_finding(finding_id, tenant_id)
        if existing is not None:
            return existing
        intel = ThreatIntelligence(
            tenant_id=tenant_id,
            finding_id=finding_id,
            cve_ids=[c.upper() for c in (cve_ids or [])],
            first_seen_at=utc_now(),
            last_updated_at=utc_now(),
        )
        return self._repo.save_intelligence(
            intel,
            actor=actor,
            change_summary="Enrichment envelope created for finding",
        )

    def enrich_finding(
        self,
        *,
        tenant_id: UUID,
        finding_id: UUID,
        cve_ids: Optional[Sequence[str]] = None,
        technique_ids: Optional[Sequence[str]] = None,
        ioc_values: Optional[Sequence[str]] = None,
        actor: Optional[str] = None,
    ) -> ThreatIntelligence:
        """
        Full enrichment pass for a finding.

        Steps: ensure envelope → CVE enrich → MITRE map → exploit analyze
        → optional IOC correlate.
        """

        intel = self.get_or_create_for_finding(
            tenant_id=tenant_id,
            finding_id=finding_id,
            cve_ids=cve_ids,
            actor=actor,
        )
        ids = list({*[c.upper() for c in (cve_ids or [])], *intel.cve_ids})
        if ids:
            intel = self._cve.enrich_from_cve_ids(intel, ids, actor=actor)

        if technique_ids or intel.mitre_techniques:
            tech_ids = list(
                {
                    *(technique_ids or []),
                    *[t.technique_id for t in intel.mitre_techniques],
                }
            )
            intel = self._mitre.apply_to_intelligence(
                intel,
                technique_ids=tech_ids,
                actor=actor,
                persist=True,
            )

        intel = self._exploit.apply(intel, actor=actor, persist=True)

        if ioc_values and self._ioc is not None:
            intel = self._ioc.apply_to_intelligence(
                intel, ioc_values, actor=actor, persist=True
            )

        if self._audit:
            self._audit.log(
                tenant_id=tenant_id,
                action=AuditAction.FINDING_ENRICHED,
                message=f"Finding {finding_id} enriched",
                actor=actor,
                details={
                    "finding_id": str(finding_id),
                    "intel_id": str(intel.id),
                    "cve_count": len(intel.cve_ids),
                    "actively_exploited": intel.exploit.actively_exploited,
                },
            )
        return intel

    def attach_threat_actor(
        self,
        intel_id: UUID,
        tenant_id: UUID,
        actor_profile: ThreatActor,
        *,
        actor: Optional[str] = None,
    ) -> ThreatIntelligence:
        intel = self._repo.get_intelligence(intel_id, tenant_id)
        by_id = {a.id: a for a in intel.threat_actors}
        by_id[actor_profile.id] = actor_profile
        intel.threat_actors = list(by_id.values())
        return self._repo.save_intelligence(
            intel,
            actor=actor,
            change_summary=f"Threat actor attached: {actor_profile.name}",
        )

    def attach_malware(
        self,
        intel_id: UUID,
        tenant_id: UUID,
        malware: MalwareFamily,
        *,
        actor: Optional[str] = None,
    ) -> ThreatIntelligence:
        intel = self._repo.get_intelligence(intel_id, tenant_id)
        by_id = {m.id: m for m in intel.malware_families}
        by_id[malware.id] = malware
        intel.malware_families = list(by_id.values())
        return self._repo.save_intelligence(
            intel,
            actor=actor,
            change_summary=f"Malware family attached: {malware.name}",
        )

    def attach_campaign(
        self,
        intel_id: UUID,
        tenant_id: UUID,
        campaign: Campaign,
        *,
        actor: Optional[str] = None,
    ) -> ThreatIntelligence:
        intel = self._repo.get_intelligence(intel_id, tenant_id)
        by_id = {c.id: c for c in intel.campaigns}
        by_id[campaign.id] = campaign
        intel.campaigns = list(by_id.values())
        return self._repo.save_intelligence(
            intel,
            actor=actor,
            change_summary=f"Campaign attached: {campaign.name}",
        )

    def search(
        self,
        filters: ThreatIntelSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[ThreatIntelligence]:
        return self._repo.search_intelligence(filters, page or PageRequest())

    def get(self, intel_id: UUID, tenant_id: UUID) -> ThreatIntelligence:
        return self._repo.get_intelligence(intel_id, tenant_id)
