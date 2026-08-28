"""ThreatIntelRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from threat_intelligence.domain.history import ThreatIntelHistory, ThreatIntelVersion
from threat_intelligence.domain.models import CVERecord, ThreatIntelligence
from threat_intelligence.query.filters import CVESearchFilter, ThreatIntelSearchFilter
from threat_intelligence.query.pagination import Page, PageRequest


class ThreatIntelRepository(ABC):
    """Persistence port for enrichment envelopes and CVE catalog."""

    @abstractmethod
    def save_intelligence(
        self,
        intel: ThreatIntelligence,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Threat intelligence persisted",
    ) -> ThreatIntelligence:
        ...

    @abstractmethod
    def get_intelligence(
        self,
        intel_id: UUID,
        tenant_id: UUID,
    ) -> ThreatIntelligence:
        ...

    @abstractmethod
    def find_by_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[ThreatIntelligence]:
        ...

    @abstractmethod
    def search_intelligence(
        self,
        filters: ThreatIntelSearchFilter,
        page: PageRequest,
    ) -> Page[ThreatIntelligence]:
        ...

    @abstractmethod
    def list_versions(
        self,
        intel_id: UUID,
        tenant_id: UUID,
    ) -> List[ThreatIntelVersion]:
        ...

    @abstractmethod
    def list_history(
        self,
        intel_id: UUID,
        tenant_id: UUID,
    ) -> List[ThreatIntelHistory]:
        ...

    @abstractmethod
    def save_cve(
        self,
        record: CVERecord,
        *,
        actor: Optional[str] = None,
    ) -> CVERecord:
        ...

    @abstractmethod
    def get_cve(
        self,
        cve_id: str,
        *,
        tenant_id: Optional[UUID] = None,
        include_global: bool = True,
    ) -> CVERecord:
        ...

    @abstractmethod
    def search_cves(
        self,
        filters: CVESearchFilter,
        page: PageRequest,
    ) -> Page[CVERecord]:
        ...
