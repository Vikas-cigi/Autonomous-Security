"""AIUsageService — token and estimated cost tracking."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ai_harness.domain.models import AIProviderResult, AIUsageMetrics
from ai_harness.domain.weights import COST_PER_1K_TOKENS_USD


class AIUsageService:
    """Normalize provider usage counters and estimate cost."""

    def from_provider_result(self, result: AIProviderResult) -> AIUsageMetrics:
        prompt_tokens, completion_tokens, total_tokens = self._extract_tokens(result.usage)
        cost = self._estimate_cost(result.provider, total_tokens)
        return AIUsageMetrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            latency_ms=result.latency_ms,
            provider=result.provider,
            model=result.model,
        )

    def merge(self, *metrics: AIUsageMetrics) -> AIUsageMetrics:
        return AIUsageMetrics(
            prompt_tokens=sum(m.prompt_tokens for m in metrics),
            completion_tokens=sum(m.completion_tokens for m in metrics),
            total_tokens=sum(m.total_tokens for m in metrics),
            estimated_cost_usd=round(sum(m.estimated_cost_usd for m in metrics), 6),
            latency_ms=round(sum(m.latency_ms for m in metrics), 3),
            provider=metrics[-1].provider if metrics else None,
            model=metrics[-1].model if metrics else None,
        )

    @staticmethod
    def _extract_tokens(usage: Dict[str, Any]) -> tuple[int, int, int]:
        prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion = int(
            usage.get("completion_tokens") or usage.get("output_tokens") or 0
        )
        total = int(usage.get("total_tokens") or (prompt + completion))
        return max(0, prompt), max(0, completion), max(0, total)

    @staticmethod
    def _estimate_cost(provider: Optional[str], total_tokens: int) -> float:
        key = (provider or "default").lower()
        rate = COST_PER_1K_TOKENS_USD.get(key, COST_PER_1K_TOKENS_USD["default"])
        return round((total_tokens / 1000.0) * rate, 6)
