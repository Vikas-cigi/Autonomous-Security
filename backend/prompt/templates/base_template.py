"""
Abstract base for prompt templates.

Templates turn ``AIContext`` into a provider-ready ``Prompt``. Each template
owns formatting rules for a decision path (chat, RAG, tools, agents).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from context.models import AIContext
from prompt.models import Prompt


class BasePromptTemplate(ABC):
    """
    Interface for prompt assembly strategies.

    SOLID notes:
        - Single Responsibility: format one style of prompt.
        - Open/Closed: new templates subclass this without changing PromptBuilder.
        - Liskov: all templates honor ``build(context) -> Prompt``.
        - Dependency Inversion: PromptBuilder depends on this abstraction.
    """

    @property
    @abstractmethod
    def template_name(self) -> str:
        """Stable identifier recorded in ``Prompt.metadata``."""

    @abstractmethod
    def build(self, context: AIContext) -> Prompt:
        """
        Build a ``Prompt`` from assembled context.

        Args:
            context: Output of ContextManager for this request.

        Returns:
            Prompt: Provider-ready messages and metadata.
        """
