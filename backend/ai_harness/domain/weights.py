"""Harness configuration constants."""

from __future__ import annotations

from typing import Dict

ALGORITHM_VERSION = "1.0.0"

# Rough USD per 1K tokens by provider family (planning estimates only).
COST_PER_1K_TOKENS_USD: Dict[str, float] = {
    "llama": 0.0,
    "openai": 0.005,
    "anthropic": 0.008,
    "default": 0.002,
}

DEFAULT_FALLBACK_ORDER = ("llama", "openai", "anthropic")
