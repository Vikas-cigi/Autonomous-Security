"""Cross-scanner correlation service."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence
from uuid import UUID, uuid4

from models.security_finding import SecurityFindingObject
from evidence_repository.fingerprint import correlation_key
from evidence_repository.interfaces.repository import EvidenceRepository
from evidence_repository.query.filters import FindingSearchFilter
from evidence_repository.query.pagination import PageRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorrelationGroup:
    """A set of findings believed to describe the same underlying issue."""

    correlation_group_id: UUID
    correlation_key: str
    finding_ids: tuple[UUID, ...]
    tenant_id: UUID


class CorrelationService:
    """
    Correlate findings across scanners for the same tenant/asset issue.

    Uses CVE+asset when available; otherwise title/type/rule without tool id.
    """

    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository

    def correlate_findings(
        self,
        tenant_id: UUID,
        findings: Sequence[SecurityFindingObject],
        *,
        actor: Optional[str] = None,
        min_group_size: int = 2,
    ) -> List[CorrelationGroup]:
        """
        Group provided findings and persist correlation_group_id assignments.
        """

        buckets: Dict[str, List[SecurityFindingObject]] = defaultdict(list)
        for finding in findings:
            if finding.tenant_id != tenant_id:
                continue
            buckets[correlation_key(finding)].append(finding)

        groups: List[CorrelationGroup] = []
        for key, members in buckets.items():
            if len(members) < min_group_size:
                continue
            group_id = uuid4()
            ids = [item.id for item in members]
            # Ensure findings exist / are latest before correlating
            for item in members:
                self._repository.save_finding(
                    item,
                    actor=actor,
                    change_summary="Pre-correlation persist",
                )
            updated = self._repository.set_correlation_group(
                tenant_id,
                ids,
                group_id,
                actor=actor,
            )
            logger.info(
                "Correlated group=%s key=%s members=%s updated=%s",
                group_id,
                key,
                len(ids),
                updated,
            )
            groups.append(
                CorrelationGroup(
                    correlation_group_id=group_id,
                    correlation_key=key,
                    finding_ids=tuple(ids),
                    tenant_id=tenant_id,
                )
            )
        return groups

    def correlate_asset(
        self,
        tenant_id: UUID,
        asset_id: UUID,
        *,
        actor: Optional[str] = None,
        min_group_size: int = 2,
    ) -> List[CorrelationGroup]:
        """Load open findings for an asset and correlate across scanners."""

        page = self._repository.search_findings(
            FindingSearchFilter(tenant_id=tenant_id, asset_id=asset_id),
            PageRequest(page=1, page_size=500),
        )
        return self.correlate_findings(
            tenant_id,
            page.items,
            actor=actor,
            min_group_size=min_group_size,
        )

    def get_group(
        self,
        tenant_id: UUID,
        correlation_group_id: UUID,
    ) -> List[SecurityFindingObject]:
        """Return all findings in a correlation group."""

        return self._repository.list_correlated(tenant_id, correlation_group_id)
