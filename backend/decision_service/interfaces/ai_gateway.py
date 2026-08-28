"""AI gateway port — Context Manager → Prompt Builder → Provider Factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from decision_service.domain.models import (
    AIRequestEnvelope,
    AIResponseEnvelope,
    DecisionContext,
)


class AIDecisionGateway(ABC):
    """
    Provider-independent AI orchestration port.

    Implementations may wrap Architecture V2 ContextManager, PromptBuilder,
    and ProviderFactory without embedding business risk/trust logic.
    """

    @abstractmethod
    async def invoke(
        self,
        context: DecisionContext,
        *,
        session_id: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> tuple[AIRequestEnvelope, AIResponseEnvelope]:
        """Run AI stack and return structured request/response envelopes."""
        ...
