"""Verification history / version helpers."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from verification_engine.domain.history import VerificationHistory
from verification_engine.domain.models import VerificationResult
from verification_engine.interfaces.verification_history_repository import (
    VerificationHistoryRepository,
)
from verification_engine.interfaces.verification_repository import VerificationRepository


class VerificationHistoryService:
    def __init__(
        self,
        verification_repository: VerificationRepository,
        history_repository: Optional[VerificationHistoryRepository] = None,
    ) -> None:
        self._repo = verification_repository
        self._history = history_repository

    def list_versions(
        self, verification_id: UUID, tenant_id: UUID
    ) -> List[VerificationHistory]:
        if self._history is not None:
            return self._history.list_for_verification(verification_id, tenant_id)
        return self._repo.list_versions(verification_id, tenant_id)

    def get_version(
        self, verification_id: UUID, tenant_id: UUID, version: int
    ) -> Optional[VerificationResult]:
        if self._history is not None:
            hist = self._history.get_version(verification_id, tenant_id, version)
            return hist.snapshot if hist else None
        versions = self._repo.list_versions(verification_id, tenant_id)
        for v in versions:
            if v.version == version:
                return v.snapshot
        return None
