"""ApprovalWorkflowRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from approval_engine.domain.models import ApprovalWorkflow


class ApprovalWorkflowRepository(ABC):
    """
    Workflow rows are embedded in ApprovalRequest payload by default.

    This port allows callers to load/update workflow snapshots independently
    when needed for orchestration tooling.
    """

    @abstractmethod
    def save(
        self, approval_id: UUID, tenant_id: UUID, workflow: ApprovalWorkflow
    ) -> ApprovalWorkflow:
        ...

    @abstractmethod
    def get(
        self, approval_id: UUID, tenant_id: UUID
    ) -> Optional[ApprovalWorkflow]:
        ...
