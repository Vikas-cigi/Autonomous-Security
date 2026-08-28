"""
Context Manager — Architecture V2 context assembly orchestrator.

Responsibilities (only):
    1. Invoke registered ``BaseContextBuilder`` instances
    2. Collect their results
    3. Assemble ``AIContext``
    4. Return ``AIContext``

No domain / business logic lives here. Builders own retrieval and shaping.
This module is not wired into ``LLMService`` or FastAPI in this phase.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from context.builders.base_builder import BaseContextBuilder
from context.builders.conversation_builder import ConversationBuilder
from context.builders.memory_builder import MemoryBuilder
from context.builders.profile_builder import ProfileBuilder
from context.builders.rag_builder import RAGBuilder
from context.builders.tool_builder import ToolBuilder
from context.models import (
    AIContext,
    ContextRequest,
    MemoryContext,
    ProfileContext,
    RequestLike,
)
from decision_engine.models import DecisionResult

logger = logging.getLogger(__name__)

# Core AIContext fields that builders may populate directly.
_CORE_BUILDER_FIELDS = frozenset(
    {
        "conversation",
        "memory",
        "documents",
        "profile",
        "tool_results",
        "system_prompt",
    }
)


class ContextManager:
    """
    Pure orchestrator over a list of ``BaseContextBuilder`` instances.

    Target Architecture V2 position::

        DecisionEngine → ContextManager → PromptBuilder → ProviderFactory

    Extensibility:
        Pass additional builders (e.g. ``SemanticMemoryBuilder``,
        ``ThreatIntelBuilder``) via the ``builders`` sequence. Known
        ``field_name`` values map onto ``AIContext`` attributes; unknown
        names are collected under ``metadata["extensions"]`` — no change to
        this class required.

    Parallelism:
        Builders are invoked sequentially today. ``_collect_builder_results``
        is structured so switching to ``asyncio.gather`` is a localized swap.
    """

    def __init__(
        self,
        builders: Optional[Sequence[BaseContextBuilder]] = None,
    ) -> None:
        """
        Create a ContextManager.

        Args:
            builders: Ordered builder pipeline. Defaults to the five phase-0
                builders. Inject fakes or extras in unit tests / future wiring.
        """

        self._builders: List[BaseContextBuilder] = (
            list(builders) if builders is not None else self.default_builders()
        )
        logger.debug(
            "ContextManager initialized builder_count=%s builders=%s",
            len(self._builders),
            [type(b).__name__ for b in self._builders],
        )

    @staticmethod
    def default_builders() -> List[BaseContextBuilder]:
        """Return the default phase-0 builder pipeline."""

        return [
            ConversationBuilder(),
            MemoryBuilder(),
            RAGBuilder(),
            ProfileBuilder(),
            ToolBuilder(),
        ]

    @property
    def builders(self) -> Tuple[BaseContextBuilder, ...]:
        """Immutable view of the registered builder pipeline."""

        return tuple(self._builders)

    async def build(
        self,
        request: RequestLike,
        decision: DecisionResult,
    ) -> AIContext:
        """
        Run builders and assemble ``AIContext``.

        Args:
            request: ``ContextRequest`` or coerceable shape (normalization
                delegated to ``ContextRequest.coerce``, not business logic).
            decision: Outcome from DecisionEngine routing.

        Returns:
            AIContext: Assembled context for downstream PromptBuilder.
        """

        normalized = ContextRequest.coerce(request)

        logger.info(
            "ContextManager.build start session_id=%s decision=%s builders=%s",
            normalized.session_id,
            decision.decision_type.value,
            len(self._builders),
        )

        slices = await self._collect_builder_results(normalized, decision)
        context = self._assemble_context(normalized, decision, slices)

        logger.info(
            "ContextManager.build complete version=%s extensions=%s",
            context.version,
            list(context.metadata.get("extensions", {}).keys()),
        )
        return context

    async def _collect_builder_results(
        self,
        request: ContextRequest,
        decision: DecisionResult,
    ) -> List[Tuple[str, Any]]:
        """
        Invoke each builder and collect ``(field_name, value)`` pairs.

        Sequential awaits today. To parallelize later with minimal change::

            # return list(zip(
            #     (b.field_name for b in self._builders),
            #     await asyncio.gather(
            #         *(b.build(request, decision) for b in self._builders)
            #     ),
            # ))
        """

        results: List[Tuple[str, Any]] = []

        for builder in self._builders:
            field = builder.field_name
            logger.debug(
                "ContextManager invoking builder=%s field=%s",
                type(builder).__name__,
                field,
            )
            value = await builder.build(request, decision)
            results.append((field, value))

        return results

    def _assemble_context(
        self,
        request: ContextRequest,
        decision: DecisionResult,
        slices: Sequence[Tuple[str, Any]],
    ) -> AIContext:
        """
        Map builder outputs onto ``AIContext`` fields.

        Assembly only — no retrieval, filtering, or domain rules.
        """

        core: Dict[str, Any] = {
            "conversation": [],
            "memory": MemoryContext(),
            "documents": [],
            "profile": ProfileContext(),
            "tool_results": [],
            "system_prompt": None,
        }
        extensions: Dict[str, Any] = {}
        builder_order: List[str] = []

        for field, value in slices:
            builder_order.append(field)
            if field in _CORE_BUILDER_FIELDS:
                core[field] = value
            else:
                extensions[field] = value

        return AIContext(
            version="1.0",
            request=request,
            conversation=core["conversation"],
            memory=core["memory"],
            documents=core["documents"],
            profile=core["profile"],
            tool_results=core["tool_results"],
            system_prompt=core["system_prompt"],
            metadata={
                "manager": self.__class__.__name__,
                "builder_order": builder_order,
                "extensions": extensions,
            },
            decision=decision,
        )
