"""VerificationHistoryRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from verification_engine.domain.history import VerificationHistory


class VerificationHistoryRepository(ABC):
    @abstractmethod
    def append(self, history: VerificationHistory) -> VerificationHistory:
        ...

    @abstractmethod
    def list_for_verification(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationHistory]:
        ...

    @abstractmethod
    def get_version(
        self, verification_id: UUID, tenant_id: UUID, version: int
    ) -> Optional[VerificationHistory]:
        ...
