"""ConfidenceRepository port — store/query explainable confidence factors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from trust_scoring.domain.models import ConfidenceFactor
from trust_scoring.query.filters import ConfidenceFactorSearchFilter
from trust_scoring.query.pagination import Page, PageRequest


class ConfidenceRepository(ABC):
    """Persistence port for confidence factors linked to assessments."""

    @abstractmethod
    def replace_factors(
        self,
        *,
        assessment_id: UUID,
        tenant_id: UUID,
        finding_id: UUID,
        factors: List[ConfidenceFactor],
        actor: Optional[str] = None,
    ) -> List[ConfidenceFactor]:
        ...

    @abstractmethod
    def list_factors(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> List[ConfidenceFactor]:
        ...

    @abstractmethod
    def search_factors(
        self,
        filters: ConfidenceFactorSearchFilter,
        page: PageRequest,
    ) -> Page[ConfidenceFactor]:
        ...
