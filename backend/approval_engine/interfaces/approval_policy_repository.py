"""ApprovalPolicyRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from approval_engine.domain.models import ApprovalPolicy
from approval_engine.query.filters import ApprovalPolicySearchFilter
from approval_engine.query.pagination import Page, PageRequest


class ApprovalPolicyRepository(ABC):
    @abstractmethod
    def save(self, policy: ApprovalPolicy) -> ApprovalPolicy:
        ...

    @abstractmethod
    def get(self, policy_id: UUID, tenant_id: UUID) -> ApprovalPolicy:
        ...

    @abstractmethod
    def find_default(self, tenant_id: UUID) -> Optional[ApprovalPolicy]:
        ...

    @abstractmethod
    def search(
        self,
        filters: ApprovalPolicySearchFilter,
        page: PageRequest,
    ) -> Page[ApprovalPolicy]:
        ...

    @abstractmethod
    def list_for_tenant(self, tenant_id: UUID) -> List[ApprovalPolicy]:
        ...
