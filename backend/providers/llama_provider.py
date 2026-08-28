"""
llama.cpp / OpenAI-compatible provider.

V1 compatibility:
    ``chat`` and ``stream_chat`` keep their existing signatures and return
    shapes so ``LLMService`` continues to work unchanged.

V2:
    ``generate(prompt) -> AIResponse`` is the Architecture V2 entry point.
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from core.config import settings
from prompt.models import Prompt, ProviderHints
from providers.base_provider import BaseProvider
from providers.exceptions import (
    LlamaProviderError,
    ProviderRequestError,
    ProviderResponseError,
)
from providers.models import AIResponse

logger = logging.getLogger(__name__)


class LlamaProvider(BaseProvider):
    """
    HTTP client for an OpenAI-compatible llama.cpp (or similar) server.

    Args:
        base_url: Upstream base URL. Defaults to ``settings.LLAMA_BASE_URL``.
        model_name: Model label for ``AIResponse.model``. Defaults to
            ``settings.MODEL_NAME``.
        timeout: Non-stream request timeout in seconds.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: float = 300.0,
    ) -> None:
        self.base_url = (base_url or settings.LLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.MODEL_NAME
        self.timeout = timeout
        logger.debug(
            "LlamaProvider initialized base_url=%s model=%s",
            self.base_url,
            self.model_name,
        )

    @property
    def provider_name(self) -> str:
        """Return the factory key for this provider."""

        return "llama"

    # ------------------------------------------------------------------
    # Architecture V2
    # ------------------------------------------------------------------

    async def generate(self, prompt: Prompt) -> AIResponse:
        """
        Run a non-streaming completion from a ``Prompt``.

        Args:
            prompt: Provider-ready prompt from PromptBuilder.

        Returns:
            AIResponse with text, usage, and latency metadata.
        """

        messages = prompt.as_openai_messages()
        logger.info(
            "LlamaProvider.generate message_count=%s",
            len(messages),
        )

        start = time.perf_counter()
        try:
            result = await self._post_chat_completion(
                messages=messages,
                stream=False,
                hints=prompt.provider_hints,
            )
        except httpx.HTTPError as exc:
            logger.exception("LlamaProvider.generate transport failure")
            raise ProviderRequestError(
                f"LlamaProvider request failed: {exc}",
                provider=self.provider_name,
                details=str(exc),
            ) from exc

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        text, finish_reason, usage = self._extract_completion(result)

        response = AIResponse(
            text=text,
            provider=self.provider_name,
            model=result.get("model") or self.model_name,
            usage=usage,
            finish_reason=finish_reason,
            metadata={
                "latency_ms": latency_ms,
                "base_url": self.base_url,
                "prompt_metadata": prompt.metadata,
            },
        )
        logger.info(
            "LlamaProvider.generate complete latency_ms=%s finish_reason=%s",
            latency_ms,
            finish_reason,
        )
        return response

    # ------------------------------------------------------------------
    # V1 API used by LLMService (unchanged contracts)
    # ------------------------------------------------------------------

    async def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Legacy non-streaming chat used by ``LLMService``.

        Returns:
            Dict with ``answer``, ``usage``, and ``latency`` (milliseconds).
        """

        start = time.perf_counter()

        payload = {
            "messages": messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=300) as client:

            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            )

            response.raise_for_status()

            result = response.json()

        latency = round((time.perf_counter() - start) * 1000, 2)

        choices = result.get("choices", [])

        if not choices:
            raise Exception("No choices returned from llama.cpp")

        message = choices[0].get("message", {})

        # Support both normal and reasoning models
        answer = (
            message.get("content")
            or message.get("reasoning_content")
            or ""
        )

        return {
            "answer": answer,
            "usage": result.get("usage", {}),
            "latency": latency,
        }

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
    ) -> AsyncIterator[str]:
        """
        Legacy streaming chat used by ``LLMService``.

        Yields raw SSE lines from the upstream server.
        """

        payload = {
            "messages": messages,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=None) as client:

            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            ) as response:

                response.raise_for_status()

                async for line in response.aiter_lines():

                    if line:
                        yield line

    # ------------------------------------------------------------------
    # Internals (V2)
    # ------------------------------------------------------------------

    async def _post_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        *,
        stream: bool,
        hints: Optional[ProviderHints] = None,
    ) -> Dict[str, Any]:
        """POST to ``/v1/chat/completions`` and return parsed JSON."""

        payload: Dict[str, Any] = {
            "messages": messages,
            "stream": stream,
        }
        if hints is not None:
            if hints.temperature is not None:
                payload["temperature"] = hints.temperature
            if hints.max_tokens is not None:
                payload["max_tokens"] = hints.max_tokens
            if hints.top_p is not None:
                payload["top_p"] = hints.top_p
            if hints.stop is not None:
                payload["stop"] = hints.stop
            if hints.extra:
                payload.update(hints.extra)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def _extract_completion(
        self,
        result: Dict[str, Any],
    ) -> tuple[str, Optional[str], Dict[str, Any]]:
        """Parse assistant text, finish reason, and usage from upstream JSON."""

        choices = result.get("choices", [])
        if not choices:
            raise ProviderResponseError(
                "No choices returned from llama.cpp",
                provider=self.provider_name,
            )

        choice = choices[0]
        message = choice.get("message", {}) or {}
        text = (
            message.get("content")
            or message.get("reasoning_content")
            or ""
        )
        if text == "" and not message:
            raise LlamaProviderError(
                "Empty message payload from llama.cpp",
                provider=self.provider_name,
                details=choice,
            )

        finish_reason = choice.get("finish_reason")
        usage = result.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {"raw": usage}

        return text, finish_reason, usage
