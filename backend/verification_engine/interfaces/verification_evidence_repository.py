"""VerificationEvidenceRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from verification_engine.domain.models import VerificationEvidence
from verification_engine.query.filters import VerificationEvidenceSearchFilter
from verification_engine.query.pagination import Page, PageRequest


class VerificationEvidenceRepository(ABC):
    @abstractmethod
    def save_many(
        self,
        verification_id: UUID,
        tenant_id: UUID,
        evidence: List[VerificationEvidence],
    ) -> List[VerificationEvidence]:
        ...

    @abstractmethod
    def list_for_verification(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationEvidence]:
        ...

    @abstractmethod
    def search(
        self,
        filters: VerificationEvidenceSearchFilter,
        page: PageRequest,
    ) -> Page[VerificationEvidence]:
        ...
