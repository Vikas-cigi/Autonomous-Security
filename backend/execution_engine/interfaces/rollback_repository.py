"""RollbackRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from execution_engine.domain.models import RollbackExecution


class RollbackRepository(ABC):
    @abstractmethod
    def save(
        self, execution_id: UUID, tenant_id: UUID, rollback: RollbackExecution
    ) -> RollbackExecution:
        ...

    @abstractmethod
    def get(
        self, execution_id: UUID, tenant_id: UUID
    ) -> Optional[RollbackExecution]:
        ...
