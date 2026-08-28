"""Search facade over EvidenceRepository with audit-friendly defaults."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from models.enums import FindingStatus, Severity, SourceTool
from models.security_finding import SecurityFindingObject
from evidence_repository.domain.enums import LifecycleState
from evidence_repository.interfaces.repository import EvidenceRepository
from evidence_repository.query.filters import FindingSearchFilter
from evidence_repository.query.pagination import Page, PageRequest

logger = logging.getLogger(__name__)


class SearchService:
    """
    Advanced querying API for findings.

    Always requires ``tenant_id`` — multi-tenant isolation is non-negotiable.
    """

    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository

    def search(
        self,
        filters: FindingSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[SecurityFindingObject]:
        """Execute a filtered, paginated search."""

        request = page or PageRequest()
        logger.debug(
            "SearchService.search tenant=%s page=%s size=%s",
            filters.tenant_id,
            request.page,
            request.page_size,
        )
        return self._repository.search_findings(filters, request)

    def by_severity(
        self,
        tenant_id: UUID,
        severities: list[Severity],
        *,
        page: Optional[PageRequest] = None,
        asset_id: Optional[UUID] = None,
    ) -> Page[SecurityFindingObject]:
        return self.search(
            FindingSearchFilter(
                tenant_id=tenant_id,
                asset_id=asset_id,
                severities=severities,
            ),
            page,
        )

    def by_scanner(
        self,
        tenant_id: UUID,
        scanners: list[SourceTool],
        *,
        page: Optional[PageRequest] = None,
    ) -> Page[SecurityFindingObject]:
        return self.search(
            FindingSearchFilter(tenant_id=tenant_id, scanners=scanners),
            page,
        )

    def by_lifecycle(
        self,
        tenant_id: UUID,
        lifecycles: list[LifecycleState],
        *,
        page: Optional[PageRequest] = None,
    ) -> Page[SecurityFindingObject]:
        return self.search(
            FindingSearchFilter(tenant_id=tenant_id, lifecycles=lifecycles),
            page,
        )

    def by_status(
        self,
        tenant_id: UUID,
        statuses: list[FindingStatus],
        *,
        page: Optional[PageRequest] = None,
    ) -> Page[SecurityFindingObject]:
        return self.search(
            FindingSearchFilter(tenant_id=tenant_id, statuses=statuses),
            page,
        )

    def open_findings(
        self,
        tenant_id: UUID,
        *,
        page: Optional[PageRequest] = None,
    ) -> Page[SecurityFindingObject]:
        """Convenience: lifecycle OPEN findings."""

        return self.by_lifecycle(
            tenant_id,
            [LifecycleState.OPEN],
            page=page,
        )
