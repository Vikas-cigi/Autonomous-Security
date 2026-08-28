"""VerificationAuditRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from verification_engine.domain.history import VerificationAuditRecord
from verification_engine.query.filters import VerificationAuditSearchFilter
from verification_engine.query.pagination import Page, PageRequest


class VerificationAuditRepository(ABC):
    @abstractmethod
    def append(self, record: VerificationAuditRecord) -> VerificationAuditRecord:
        ...

    @abstractmethod
    def list_for_verification(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationAuditRecord]:
        ...

    @abstractmethod
    def search(
        self,
        filters: VerificationAuditSearchFilter,
        page: PageRequest,
    ) -> Page[VerificationAuditRecord]:
        ...
