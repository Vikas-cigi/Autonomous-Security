"""
Prompt Builder — Architecture V2 prompt assembly facade.

Transforms ``AIContext`` into a provider-ready ``Prompt`` via injectable
templates. Not wired into ``LLMService``, ``PromptService``, or FastAPI.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from context.models import AIContext
from decision_engine.models import DecisionType
from prompt.models import Prompt
from prompt.templates.agent_template import AgentTemplate
from prompt.templates.base_template import BasePromptTemplate
from prompt.templates.chat_template import ChatTemplate
from prompt.templates.rag_template import RAGTemplate
from prompt.templates.tool_template import ToolTemplate

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Orchestrates prompt templates for Architecture V2.

    Default behavior: always use ``ChatTemplate`` (phase 0). Optional
    ``templates`` map enables decision-aware selection later without
    changing the ``build(context)`` contract.

    SOLID notes:
        - Single Responsibility: select template and return Prompt.
        - Open/Closed: inject new templates via constructor.
        - Dependency Inversion: depends on ``BasePromptTemplate``.
    """

    def __init__(
        self,
        default_template: Optional[BasePromptTemplate] = None,
        templates: Optional[Dict[DecisionType, BasePromptTemplate]] = None,
    ) -> None:
        """
        Args:
            default_template: Template used when no decision-specific entry
                matches. Defaults to ``ChatTemplate``.
            templates: Optional mapping from ``DecisionType`` → template.
                Unused for routing in phase 0 (default always wins) but
                reserved for future decision-aware selection. Placeholders
                can be registered here for tests.
        """

        self._default_template: BasePromptTemplate = (
            default_template or ChatTemplate()
        )
        self._templates: Dict[DecisionType, BasePromptTemplate] = dict(
            templates or {}
        )

        logger.debug(
            "PromptBuilder initialized default=%s registered=%s",
            type(self._default_template).__name__,
            {k.value: type(v).__name__ for k, v in self._templates.items()},
        )

    @property
    def default_template(self) -> BasePromptTemplate:
        """Return the default template (useful for tests)."""

        return self._default_template

    @staticmethod
    def placeholder_registry() -> Dict[DecisionType, BasePromptTemplate]:
        """
        Convenience registry of phase-0 templates including placeholders.

        Not applied automatically — callers may pass this to ``templates``
        when enabling decision-aware routing in a later phase.
        """

        return {
            DecisionType.CHAT: ChatTemplate(),
            DecisionType.RAG: RAGTemplate(),
            DecisionType.TOOL: ToolTemplate(),
            DecisionType.AGENT: AgentTemplate(),
            DecisionType.MEMORY: ChatTemplate(),
            DecisionType.UNKNOWN: ChatTemplate(),
        }

    def build(self, context: AIContext) -> Prompt:
        """
        Build a ``Prompt`` from ``AIContext``.

        Phase 0: always delegates to the default ``ChatTemplate``.

        Args:
            context: Assembled context from ContextManager.

        Returns:
            Prompt: Provider-ready system text, messages, and metadata.
        """

        template = self._select_template(context)
        logger.info(
            "PromptBuilder.build using template=%s decision=%s",
            template.template_name,
            context.decision.decision_type.value,
        )

        prompt = template.build(context)
        prompt.metadata = {
            **prompt.metadata,
            "builder": self.__class__.__name__,
            "selected_template": template.template_name,
            "selection_mode": "default_chat",
        }

        logger.info(
            "PromptBuilder.build complete message_count=%s",
            len(prompt.messages),
        )
        return prompt

    def _select_template(self, context: AIContext) -> BasePromptTemplate:
        """
        Choose which template to run.

        Phase 0 policy: always return ``default_template`` (ChatTemplate).
        Future policy (commented intent)::

            return self._templates.get(
                context.decision.decision_type,
                self._default_template,
            )
        """

        _ = context  # decision-aware selection deferred
        return self._default_template
