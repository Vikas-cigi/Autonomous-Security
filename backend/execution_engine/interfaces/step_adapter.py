"""Infrastructure step executor port — future provider integrations plug in here."""

from __future__ import annotations

from abc import ABC, abstractmethod

from execution_engine.domain.models import (
    ExecutionContext,
    ExecutionStep,
    StepExecutionResult,
)


class StepInfrastructureAdapter(ABC):
    """
    Port for real infrastructure execution.

    Business orchestration never talks to cloud/provider SDKs directly.
    Default implementation records deterministic success without side effects.
    """

    @abstractmethod
    def execute_step(
        self,
        step: ExecutionStep,
        *,
        context: ExecutionContext,
        attempt: int,
    ) -> StepExecutionResult:
        ...
