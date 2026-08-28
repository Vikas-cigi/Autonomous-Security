"""
Tool prompt template — formats scan / tool results for the LLM.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from context.models import AIContext
from prompt.models import Prompt, PromptMessage, ProviderHints
from prompt.templates.base_template import BasePromptTemplate

logger = logging.getLogger(__name__)


def _serialize(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, default=str)
    except TypeError:
        return str(value)


class ToolTemplate(BasePromptTemplate):
    """Serialize ``tool_results`` into a cybersecurity operator prompt."""

    @property
    def template_name(self) -> str:
        return "tool"

    def build(self, context: AIContext) -> Prompt:
        logger.info(
            "ToolTemplate.build tool_result_count=%s",
            len(context.tool_results),
        )
        blocks = []
        for idx, result in enumerate(context.tool_results, start=1):
            blocks.append(
                f"### Tool {idx}: {result.tool_name} [{result.status}]\n"
                f"{_serialize(result.output)}"
            )
        tool_block = "\n\n".join(blocks) if blocks else "(no tool results)"

        system = (
            "You are RavenX, the Xolaris cybersecurity assistant. "
            "A security tool just ran. Summarize the scan outcome for the operator: "
            "findings (severity + title), whether Trust/Risk/Decision/Plan ran, "
            "and the clearest next step. Be concise and factual. "
            "Do not invent findings that are not in the tool results."
        )
        user = (
            f"Operator request:\n{context.request.message}\n\n"
            f"Tool results:\n{tool_block}"
        )
        return Prompt(
            system_prompt=system,
            messages=[
                PromptMessage(role="system", content=system),
                PromptMessage(role="user", content=user),
            ],
            metadata={
                "template": self.template_name,
                "decision_type": context.decision.decision_type.value,
                "status": "ready",
                "tool_result_count": len(context.tool_results),
            },
            provider_hints=ProviderHints(),
        )
