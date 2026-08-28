"""
Chat prompt template — working phase-0 implementation.

Assembles system prompt + conversation history + current user message,
mirroring the shape historically produced by ``PromptService`` without
modifying or calling that service.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from context.models import AIContext
from prompt.models import Prompt, PromptMessage, ProviderHints
from prompt.templates.base_template import BasePromptTemplate

logger = logging.getLogger(__name__)


class ChatTemplate(BasePromptTemplate):
    """
    Default conversational prompt template.

    System prompt resolution order:
        1. ``context.system_prompt`` when set
        2. Injected ``system_prompt`` string
        3. Contents of ``prompts/cyber_system.txt`` (same source file as
           PromptService, read independently — PromptService is untouched)
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        system_prompt_path: Optional[Path] = None,
    ) -> None:
        """
        Args:
            system_prompt: Optional override of the default system text.
            system_prompt_path: Optional path to a system prompt file.
                Defaults to ``backend/prompts/cyber_system.txt``.
        """

        self._injected_system_prompt = system_prompt
        self._system_prompt_path = system_prompt_path or (
            Path(__file__).resolve().parent.parent.parent / "prompts" / "cyber_system.txt"
        )
        self._cached_file_prompt: Optional[str] = None
        logger.debug(
            "ChatTemplate initialized path=%s injected=%s",
            self._system_prompt_path,
            system_prompt is not None,
        )

    @property
    def template_name(self) -> str:
        """Return the template identifier."""

        return "chat"

    def build(self, context: AIContext) -> Prompt:
        """
        Build a standard chat completion prompt from ``AIContext``.

        Args:
            context: Assembled context (conversation + current request).

        Returns:
            Prompt with system + history + user messages.
        """

        system_prompt = self._resolve_system_prompt(context)
        messages: List[PromptMessage] = [
            PromptMessage(role="system", content=system_prompt)
        ]

        for turn in context.conversation:
            messages.append(
                PromptMessage(role=turn.role, content=turn.content)
            )

        user_message = context.request.message
        messages.append(PromptMessage(role="user", content=user_message))

        prompt = Prompt(
            system_prompt=system_prompt,
            messages=messages,
            metadata={
                "template": self.template_name,
                "decision_type": context.decision.decision_type.value,
                "session_id": context.request.session_id,
                "history_turns": len(context.conversation),
                "message_count": len(messages),
                "context_version": context.version,
            },
            provider_hints=ProviderHints(),
        )

        logger.info(
            "ChatTemplate.build complete history_turns=%s message_count=%s",
            len(context.conversation),
            len(messages),
        )
        return prompt

    def _resolve_system_prompt(self, context: AIContext) -> str:
        """Pick the system prompt text using the documented precedence."""

        if context.system_prompt:
            logger.debug("ChatTemplate using context.system_prompt override")
            return context.system_prompt

        if self._injected_system_prompt is not None:
            logger.debug("ChatTemplate using injected system_prompt")
            return self._injected_system_prompt

        if self._cached_file_prompt is None:
            self._cached_file_prompt = self._system_prompt_path.read_text(
                encoding="utf-8"
            )
            logger.debug(
                "ChatTemplate loaded system prompt from %s (%s chars)",
                self._system_prompt_path,
                len(self._cached_file_prompt),
            )

        return self._cached_file_prompt
