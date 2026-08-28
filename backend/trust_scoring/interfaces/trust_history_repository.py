"""TrustHistoryRepository port — append-only audit history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from trust_scoring.domain.history import TrustAuditRecord
from trust_scoring.query.filters import TrustHistorySearchFilter
from trust_scoring.query.pagination import Page, PageRequest


class TrustHistoryRepository(ABC):
    """Append-only history for trust assessments."""

    @abstractmethod
    def append(
        self,
        record: TrustAuditRecord,
    ) -> TrustAuditRecord:
        ...

    @abstractmethod
    def list_for_assessment(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> List[TrustAuditRecord]:
        ...

    @abstractmethod
    def list_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[TrustAuditRecord]:
        ...

    @abstractmethod
    def search(
        self,
        filters: TrustHistorySearchFilter,
        page: PageRequest,
    ) -> Page[TrustAuditRecord]:
        ...
