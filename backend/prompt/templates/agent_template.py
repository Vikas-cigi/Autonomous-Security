"""
Agent prompt template — placeholder for Architecture V2.

Future versions will format multi-step agent plans, scratchpads, and
intermediate observations into the message list.
"""

from __future__ import annotations

import logging

from context.models import AIContext
from prompt.models import Prompt, PromptMessage, ProviderHints
from prompt.templates.base_template import BasePromptTemplate

logger = logging.getLogger(__name__)


class AgentTemplate(BasePromptTemplate):
    """
    Placeholder template for agentic / multi-step prompts.

    Planning and tool loops are out of scope; this layer only formats
    agent-oriented context when implemented.
    """

    @property
    def template_name(self) -> str:
        """Return the template identifier."""

        return "agent"

    def build(self, context: AIContext) -> Prompt:
        """
        Build a placeholder agent prompt.

        Args:
            context: Assembled context.

        Returns:
            Prompt marked as an agent placeholder.
        """

        logger.info(
            "AgentTemplate.build placeholder decision=%s",
            context.decision.decision_type.value,
        )
        system = (
            "AgentTemplate placeholder — agent scratchpad/plan not implemented yet."
        )
        return Prompt(
            system_prompt=system,
            messages=[
                PromptMessage(role="system", content=system),
                PromptMessage(role="user", content=context.request.message),
            ],
            metadata={
                "template": self.template_name,
                "decision_type": context.decision.decision_type.value,
                "status": "placeholder",
            },
            provider_hints=ProviderHints(),
        )
