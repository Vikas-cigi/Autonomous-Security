"""IOC correlation against the indicator store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence
from uuid import UUID

from threat_intelligence.domain.ioc import IndicatorOfCompromise
from threat_intelligence.domain.models import ThreatIntelligence
from threat_intelligence.interfaces.ioc_repository import IOCRepository
from threat_intelligence.interfaces.threat_intel_repository import ThreatIntelRepository


@dataclass
class IOCCorrelationResult:
    matched: List[IndicatorOfCompromise] = field(default_factory=list)
    unmatched_values: List[str] = field(default_factory=list)


class IOCCorrelationService:
    """Correlate observed values with stored IOCs and attach to enrichment."""

    def __init__(
        self,
        ioc_repository: IOCRepository,
        *,
        intel_repository: Optional[ThreatIntelRepository] = None,
    ) -> None:
        self._iocs = ioc_repository
        self._intel = intel_repository

    def correlate(
        self,
        *,
        tenant_id: UUID,
        values: Sequence[str],
    ) -> IOCCorrelationResult:
        normalized = [v.strip() for v in values if v and v.strip()]
        # Lowercase hashes/domains for match; keep originals for unmatched report
        candidates = list({v.lower() for v in normalized} | set(normalized))
        matched = self._iocs.match_values(
            tenant_id=tenant_id,
            normalized_values=candidates,
            include_global=True,
        )
        matched_norms = {m.normalized_value for m in matched}
        unmatched = [
            v for v in normalized if v.lower() not in matched_norms and v not in matched_norms
        ]
        return IOCCorrelationResult(matched=matched, unmatched_values=unmatched)

    def apply_to_intelligence(
        self,
        intel: ThreatIntelligence,
        values: Sequence[str],
        *,
        actor: Optional[str] = None,
        persist: bool = True,
    ) -> ThreatIntelligence:
        result = self.correlate(tenant_id=intel.tenant_id, values=values)
        ioc_ids = list({*intel.ioc_ids, *[m.id for m in result.matched]})
        intel.ioc_ids = ioc_ids

        # Pull associations from matched IOCs
        actor_ids = set()
        malware_ids = set()
        campaign_ids = set()
        for ioc in result.matched:
            actor_ids.update(ioc.threat_actor_ids)
            malware_ids.update(ioc.malware_family_ids)
            campaign_ids.update(ioc.campaign_ids)
            for cve in ioc.cve_ids:
                if cve not in intel.cve_ids:
                    intel.cve_ids.append(cve)

        if result.matched:
            intel.confidence_score = max(
                intel.confidence_score,
                max(m.confidence_score for m in result.matched),
            )
            intel.summary = (
                intel.summary
                or f"IOC correlation matched {len(result.matched)} indicator(s)"
            )

        if persist and self._intel is not None:
            return self._intel.save_intelligence(
                intel,
                actor=actor,
                change_summary=f"IOC correlation ({len(result.matched)} matches)",
            )
        return intel

    def upsert_ioc(
        self,
        ioc: IndicatorOfCompromise,
        *,
        actor: Optional[str] = None,
    ) -> IndicatorOfCompromise:
        return self._iocs.save_ioc(ioc, actor=actor)
