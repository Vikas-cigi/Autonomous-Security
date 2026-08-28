"""RemediationPlanRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from remediation_planner.domain.history import RemediationHistory
from remediation_planner.domain.models import RemediationPlan
from remediation_planner.query.filters import RemediationPlanSearchFilter
from remediation_planner.query.pagination import Page, PageRequest


class RemediationPlanRepository(ABC):
    @abstractmethod
    def save(
        self,
        plan: RemediationPlan,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Remediation plan persisted",
    ) -> RemediationPlan:
        ...

    @abstractmethod
    def get(self, plan_id: UUID, tenant_id: UUID) -> RemediationPlan:
        ...

    @abstractmethod
    def find_by_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[RemediationPlan]:
        ...

    @abstractmethod
    def find_by_decision(
        self,
        decision_id: UUID,
        tenant_id: UUID,
    ) -> Optional[RemediationPlan]:
        ...

    @abstractmethod
    def search(
        self,
        filters: RemediationPlanSearchFilter,
        page: PageRequest,
    ) -> Page[RemediationPlan]:
        ...

    @abstractmethod
    def list_versions(
        self,
        plan_id: UUID,
        tenant_id: UUID,
    ) -> List[RemediationHistory]:
        ...
