"""
RAG prompt template — placeholder for Architecture V2.

Future versions will inject retrieved ``context.documents`` into the system
or user message with citations. Phase 0 returns a minimal stub Prompt.
"""

from __future__ import annotations

import logging

from context.models import AIContext
from prompt.models import Prompt, PromptMessage, ProviderHints
from prompt.templates.base_template import BasePromptTemplate

logger = logging.getLogger(__name__)


class RAGTemplate(BasePromptTemplate):
    """
    Placeholder template for retrieval-augmented generation prompts.

    Does not perform retrieval (that belongs to ContextManager / RAGBuilder).
    Will later format documents into the prompt body.
    """

    @property
    def template_name(self) -> str:
        """Return the template identifier."""

        return "rag"

    def build(self, context: AIContext) -> Prompt:
        """
        Build a placeholder RAG prompt.

        Args:
            context: Assembled context (documents ignored in phase 0).

        Returns:
            Prompt marked as a RAG placeholder.
        """

        logger.info(
            "RAGTemplate.build placeholder document_count=%s",
            len(context.documents),
        )
        system = (
            "RAGTemplate placeholder — document grounding not implemented yet."
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
                "document_count": len(context.documents),
            },
            provider_hints=ProviderHints(),
        )
