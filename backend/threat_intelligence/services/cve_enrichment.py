"""CVE enrichment service — catalog lookup and CVSS/EPSS/KEV merge."""

from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID

from models.common import utc_now
from threat_intelligence.domain.enums import ThreatFeedProviderId
from threat_intelligence.domain.models import (
    CVERecord,
    EPSSScore,
    ExploitInformation,
    ThreatIntelligence,
)
from threat_intelligence.exceptions import CVENotFoundError
from threat_intelligence.interfaces.threat_intel_repository import ThreatIntelRepository


class CVEEnrichmentService:
    """
    Enrich findings / intel envelopes from the CVE catalog.

    Does not call external APIs; consumes records already stored via feeds
    or manual upsert.
    """

    def __init__(self, repository: ThreatIntelRepository) -> None:
        self._repo = repository

    def upsert_cve(
        self,
        record: CVERecord,
        *,
        actor: Optional[str] = None,
    ) -> CVERecord:
        return self._repo.save_cve(record, actor=actor)

    def get_cve(
        self,
        cve_id: str,
        *,
        tenant_id: Optional[UUID] = None,
    ) -> CVERecord:
        return self._repo.get_cve(cve_id, tenant_id=tenant_id, include_global=True)

    def enrich_from_cve_ids(
        self,
        intel: ThreatIntelligence,
        cve_ids: Sequence[str],
        *,
        actor: Optional[str] = None,
    ) -> ThreatIntelligence:
        """Merge catalog CVE records into an enrichment envelope."""

        records: List[CVERecord] = []
        for cve_id in cve_ids:
            try:
                records.append(
                    self._repo.get_cve(
                        cve_id,
                        tenant_id=intel.tenant_id,
                        include_global=True,
                    )
                )
            except CVENotFoundError:
                continue

        intel.cve_ids = sorted({*intel.cve_ids, *[r.cve_id for r in records]})
        # Replace/merge cve_records by cve_id
        by_id = {r.cve_id: r for r in intel.cve_records}
        for record in records:
            by_id[record.cve_id] = record
        intel.cve_records = list(by_id.values())

        # Roll up exploit / EPSS / CWE / CAPEC / MITRE
        cwe: List[str] = list(intel.cwe_ids)
        capec: List[str] = list(intel.capec_ids)
        techniques = {t.technique_id: t for t in intel.mitre_techniques}
        exploit = intel.exploit.model_copy(deep=True)
        best_epss: Optional[EPSSScore] = intel.epss
        providers = set(intel.source_providers)

        for record in records:
            for item in record.cwe_ids:
                if item not in cwe:
                    cwe.append(item)
            for item in record.capec_ids:
                if item not in capec:
                    capec.append(item)
            for tech in record.mitre_techniques:
                techniques[tech.technique_id] = tech
            providers.update(record.source_providers)
            if record.exploit.available:
                exploit.available = True
            if record.exploit.actively_exploited:
                exploit.actively_exploited = True
            if record.exploit.in_cisa_kev:
                exploit.in_cisa_kev = True
                exploit.kev_date_added = (
                    record.exploit.kev_date_added or exploit.kev_date_added
                )
                exploit.kev_due_date = (
                    record.exploit.kev_due_date or exploit.kev_due_date
                )
            if record.epss is not None:
                if best_epss is None or record.epss.score > best_epss.score:
                    best_epss = record.epss
            providers.add(ThreatFeedProviderId.INTERNAL)

        intel.cwe_ids = cwe
        intel.capec_ids = capec
        intel.mitre_techniques = list(techniques.values())
        intel.exploit = exploit
        intel.epss = best_epss
        intel.source_providers = list(providers)
        intel.last_updated_at = utc_now()
        intel.confidence_score = max(
            intel.confidence_score,
            max((r.confidence_score for r in records), default=intel.confidence_score),
        )
        if records and not intel.summary:
            titles = [r.title or r.cve_id for r in records[:3]]
            intel.summary = "CVE enrichment: " + ", ".join(titles)

        return self._repo.save_intelligence(
            intel,
            actor=actor,
            change_summary="CVE enrichment applied",
        )

    def apply_kev_flags(
        self,
        cve_id: str,
        *,
        tenant_id: Optional[UUID] = None,
        actor: Optional[str] = None,
    ) -> CVERecord:
        """Mark a CVE as CISA KEV / actively exploited (manual or feed-driven)."""

        record = self._repo.get_cve(cve_id, tenant_id=tenant_id, include_global=True)
        exploit = record.exploit or ExploitInformation()
        record.exploit = ExploitInformation(
            available=True,
            maturity=exploit.maturity,
            actively_exploited=True,
            in_cisa_kev=True,
            kev_date_added=exploit.kev_date_added or utc_now(),
            kev_due_date=exploit.kev_due_date,
            known_ransomware_use=exploit.known_ransomware_use,
            public_exploit_urls=exploit.public_exploit_urls,
            notes=exploit.notes,
        )
        if ThreatFeedProviderId.CISA_KEV not in record.source_providers:
            record.source_providers = [
                *record.source_providers,
                ThreatFeedProviderId.CISA_KEV,
            ]
        return self._repo.save_cve(record, actor=actor)
