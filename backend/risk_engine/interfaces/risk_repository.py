"""RiskRepository port — persist and retrieve RiskAssessment envelopes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from risk_engine.domain.history import RiskHistory
from risk_engine.domain.models import RiskAssessment
from risk_engine.query.filters import RiskAssessmentSearchFilter
from risk_engine.query.pagination import Page, PageRequest


class RiskRepository(ABC):
    """All methods that accept tenant_id enforce multi-tenant isolation."""

    @abstractmethod
    def save_assessment(
        self,
        assessment: RiskAssessment,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Risk assessment persisted",
    ) -> RiskAssessment:
        ...

    @abstractmethod
    def get_assessment(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> RiskAssessment:
        ...

    @abstractmethod
    def find_by_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[RiskAssessment]:
        ...

    @abstractmethod
    def search_assessments(
        self,
        filters: RiskAssessmentSearchFilter,
        page: PageRequest,
    ) -> Page[RiskAssessment]:
        ...

    @abstractmethod
    def list_versions(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> List[RiskHistory]:
        ...
