"""TrustRepository port — persist and retrieve TrustAssessment envelopes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from trust_scoring.domain.history import TrustAssessmentVersion
from trust_scoring.domain.models import TrustAssessment
from trust_scoring.query.filters import TrustAssessmentSearchFilter
from trust_scoring.query.pagination import Page, PageRequest


class TrustRepository(ABC):
    """All methods that accept tenant_id enforce multi-tenant isolation."""

    @abstractmethod
    def save_assessment(
        self,
        assessment: TrustAssessment,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Trust assessment persisted",
    ) -> TrustAssessment:
        ...

    @abstractmethod
    def get_assessment(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> TrustAssessment:
        ...

    @abstractmethod
    def find_by_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[TrustAssessment]:
        ...

    @abstractmethod
    def search_assessments(
        self,
        filters: TrustAssessmentSearchFilter,
        page: PageRequest,
    ) -> Page[TrustAssessment]:
        ...

    @abstractmethod
    def list_versions(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> List[TrustAssessmentVersion]:
        ...
