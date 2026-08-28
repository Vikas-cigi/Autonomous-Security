"""
Abstract base for all context builders.

Every builder that contributes a slice of ``AIContext`` must inherit from
``BaseContextBuilder`` and implement the async ``build`` contract. This keeps
``ContextManager`` open for extension (new builders) and closed for
modification (orchestrator stays stable).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from context.models import ContextRequest
from decision_engine.models import DecisionResult


class BaseContextBuilder(ABC):
    """
    Interface for asynchronous context builders.

    Design goals:
        - Uniform async contract for I/O-bound future backends (Redis, Qdrant,
          PostgreSQL, HTTP, MCP) without blocking the event loop.
        - ``field_name`` tells the orchestrator which ``AIContext`` attribute
          (or metadata extension key) this builder populates.
        - No knowledge of other builders — Single Responsibility.

    Example::

        class ThreatIntelBuilder(BaseContextBuilder):
            @property
            def field_name(self) -> str:
                return "threat_intel"  # lands in metadata.extensions today

            async def build(self, request, decision):
                return {"indicators": []}
    """

    @property
    @abstractmethod
    def field_name(self) -> str:
        """
        Target key on ``AIContext`` or extension namespace.

        Known core keys: ``conversation``, ``memory``, ``documents``,
        ``profile``, ``tool_results``, ``system_prompt``.
        Any other key is stored under ``AIContext.metadata["extensions"]``
        so new builders can ship without changing ``ContextManager``.
        """

    @abstractmethod
    async def build(
        self,
        request: ContextRequest,
        decision: DecisionResult,
    ) -> Any:
        """
        Asynchronously build one context slice.

        Args:
            request: Normalized inbound request.
            decision: Routing decision from DecisionEngine.

        Returns:
            Value for ``field_name`` (type depends on the builder).
        """
