"""AIReflectionService — optional second-pass reflection (no business logic)."""

from __future__ import annotations

from typing import Optional

from prompt.models import Prompt, PromptMessage
from providers.base_provider import BaseProvider

from ai_harness.domain.enums import ReflectionMode
from ai_harness.domain.models import AIReflection, AIRequest, AIValidationResult


class AIReflectionService:
    """
    Optionally ask the same provider to refine/critique a prior response.

    Reflection prompts are generic quality checks — not cybersecurity policy.
    """

    async def maybe_reflect(
        self,
        *,
        request: AIRequest,
        provider: BaseProvider,
        primary_text: str,
        validation: Optional[AIValidationResult],
    ) -> AIReflection:
        mode = request.reflection_mode
        if mode == ReflectionMode.DISABLED:
            return AIReflection(enabled=False, performed=False, notes="Reflection disabled.")

        should_run = mode == ReflectionMode.ALWAYS or (
            mode == ReflectionMode.ON_FAILURE
            and validation is not None
            and not validation.valid
        )
        if not should_run:
            return AIReflection(
                enabled=True,
                performed=False,
                notes="Reflection not required for this outcome.",
            )

        reflection_prompt = Prompt(
            system_prompt=(
                "You are a response-quality reviewer. Improve clarity and ensure "
                "the output satisfies the requested format. Do not invent business policy."
            ),
            messages=[
                PromptMessage(
                    role="user",
                    content=(
                        "Original user request:\n"
                        f"{request.message}\n\n"
                        "Prior assistant response:\n"
                        f"{primary_text}\n\n"
                        "Return an improved final answer only."
                    ),
                )
            ],
            metadata={"harness": "reflection"},
        )
        raw = await provider.generate(reflection_prompt)
        improved_text = (raw.text or "").strip()
        improved = bool(improved_text) and improved_text != primary_text.strip()
        return AIReflection(
            enabled=True,
            performed=True,
            improved=improved,
            reflection_text=improved_text or primary_text,
            notes="Reflection pass completed.",
        )
