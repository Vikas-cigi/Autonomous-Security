"""Execution Engine exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class ExecutionEngineError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class ExecutionNotFoundError(ExecutionEngineError):
    def __init__(self, execution_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Execution {execution_id} not found for tenant {tenant_id}",
            details={
                "execution_id": str(execution_id),
                "tenant_id": str(tenant_id),
            },
        )


class InvalidExecutionRequestError(ExecutionEngineError):
    """Raised when execution inputs fail structural or authorization validation."""


class ExecutionStateError(ExecutionEngineError):
    """Raised when an operation is illegal for the current execution state."""


class StepExecutionError(ExecutionEngineError):
    """Raised when a step adapter fails fatally."""
