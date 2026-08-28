"""
Prompt Builder package — Architecture V2 prompt assembly (scaffold).

Public surface:

    from prompt import PromptBuilder, Prompt
    from prompt.templates import ChatTemplate, BasePromptTemplate

This package is **not** wired into FastAPI, ``LLMService``, or
``PromptService`` yet.
"""

from prompt.models import Prompt, PromptMessage, ProviderHints
from prompt.prompt_builder import PromptBuilder
from prompt.templates.base_template import BasePromptTemplate
from prompt.templates.chat_template import ChatTemplate

__all__ = [
    "BasePromptTemplate",
    "ChatTemplate",
    "Prompt",
    "PromptBuilder",
    "PromptMessage",
    "ProviderHints",
]

__version__ = "0.1.0"
