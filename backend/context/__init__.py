"""
Context Manager package — Architecture V2 context assembly (scaffold).

Public surface:

    from context import ContextManager, AIContext, ContextRequest
    from context.builders import BaseContextBuilder

This package is **not** wired into FastAPI or ``LLMService`` yet.
"""

from context.builders.base_builder import BaseContextBuilder
from context.context_manager import ContextManager
from context.models import (
    AIContext,
    ContextRequest,
    ConversationMessage,
    DocumentChunk,
    MemoryContext,
    ProfileContext,
    ToolResult,
)

__all__ = [
    "AIContext",
    "BaseContextBuilder",
    "ContextManager",
    "ContextRequest",
    "ConversationMessage",
    "DocumentChunk",
    "MemoryContext",
    "ProfileContext",
    "ToolResult",
]

__version__ = "0.2.0"
