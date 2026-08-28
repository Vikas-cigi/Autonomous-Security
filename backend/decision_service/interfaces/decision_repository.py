"""DecisionRepository port — persist and retrieve DecisionResponse envelopes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from decision_service.domain.history import DecisionVersionRecord
from decision_service.domain.models import DecisionResponse
from decision_service.query.filters import DecisionSearchFilter
from decision_service.query.pagination import Page, PageRequest


class DecisionRepository(ABC):
    """All methods that accept tenant_id enforce multi-tenant isolation."""

    @abstractmethod
    def save(
        self,
        response: DecisionResponse,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Decision persisted",
    ) -> DecisionResponse:
        ...

    @abstractmethod
    def get(
        self,
        decision_id: UUID,
        tenant_id: UUID,
    ) -> DecisionResponse:
        ...

    @abstractmethod
    def find_by_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[DecisionResponse]:
        ...

    @abstractmethod
    def search(
        self,
        filters: DecisionSearchFilter,
        page: PageRequest,
    ) -> Page[DecisionResponse]:
        ...

    @abstractmethod
    def list_versions(
        self,
        decision_id: UUID,
        tenant_id: UUID,
    ) -> List[DecisionVersionRecord]:
        ...
