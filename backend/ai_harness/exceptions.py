"""Enterprise AI Harness exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class AIHarnessError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class AIExecutionNotFoundError(AIHarnessError):
    def __init__(self, execution_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"AI execution {execution_id} not found for tenant {tenant_id}",
            details={
                "execution_id": str(execution_id),
                "tenant_id": str(tenant_id),
            },
        )


class AIValidationError(AIHarnessError):
    """Raised when structured output validation fails hard."""


class AITimeoutError(AIHarnessError):
    """Raised when provider generation exceeds the configured timeout."""


class AIProviderExhaustedError(AIHarnessError):
    """Raised when primary and all fallback providers fail."""


class InvalidAIRequestError(AIHarnessError):
    """Raised when an AIRequest fails structural validation."""
