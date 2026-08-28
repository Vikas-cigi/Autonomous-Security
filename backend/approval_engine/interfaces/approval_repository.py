"""ApprovalRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from approval_engine.domain.history import ApprovalHistory
from approval_engine.domain.models import ApprovalRequest
from approval_engine.query.filters import ApprovalSearchFilter
from approval_engine.query.pagination import Page, PageRequest


class ApprovalRepository(ABC):
    @abstractmethod
    def save(
        self,
        request: ApprovalRequest,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Approval request persisted",
    ) -> ApprovalRequest:
        ...

    @abstractmethod
    def get(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest:
        ...

    @abstractmethod
    def find_by_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> Optional[ApprovalRequest]:
        ...

    @abstractmethod
    def search(
        self,
        filters: ApprovalSearchFilter,
        page: PageRequest,
    ) -> Page[ApprovalRequest]:
        ...

    @abstractmethod
    def list_versions(
        self, approval_id: UUID, tenant_id: UUID
    ) -> List[ApprovalHistory]:
        ...
