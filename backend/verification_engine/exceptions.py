"""Verification Engine exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class VerificationEngineError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class VerificationNotFoundError(VerificationEngineError):
    def __init__(self, verification_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Verification {verification_id} not found for tenant {tenant_id}",
            details={
                "verification_id": str(verification_id),
                "tenant_id": str(tenant_id),
            },
        )


class InvalidVerificationRequestError(VerificationEngineError):
    """Raised when verification inputs fail structural validation."""


class VerificationStateError(VerificationEngineError):
    """Raised when an operation is illegal for the current verification state."""
