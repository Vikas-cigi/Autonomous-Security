"""VerificationRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from verification_engine.domain.history import VerificationHistory
from verification_engine.domain.models import VerificationResult
from verification_engine.query.filters import VerificationSearchFilter
from verification_engine.query.pagination import Page, PageRequest


class VerificationRepository(ABC):
    @abstractmethod
    def save(
        self,
        result: VerificationResult,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Verification persisted",
    ) -> VerificationResult:
        ...

    @abstractmethod
    def get(self, verification_id: UUID, tenant_id: UUID) -> VerificationResult:
        ...

    @abstractmethod
    def find_by_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> Optional[VerificationResult]:
        ...

    @abstractmethod
    def find_by_finding(
        self, finding_id: UUID, tenant_id: UUID
    ) -> Optional[VerificationResult]:
        ...

    @abstractmethod
    def search(
        self,
        filters: VerificationSearchFilter,
        page: PageRequest,
    ) -> Page[VerificationResult]:
        ...

    @abstractmethod
    def list_versions(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationHistory]:
        ...
