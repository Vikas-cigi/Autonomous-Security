"""
Providers package — Architecture V2 provider factory (scaffold).

Public surface:

    from providers import ProviderFactory, BaseProvider, AIResponse
    from providers import LlamaProvider

V1 compatibility:
    ``from providers.llama_provider import LlamaProvider`` continues to work
    for ``LLMService``. Legacy ``chat`` / ``stream_chat`` are unchanged.
"""

from providers.base_provider import BaseProvider
from providers.exceptions import (
    AnthropicProviderError,
    LlamaProviderError,
    OpenAIProviderError,
    ProviderConfigurationError,
    ProviderError,
    ProviderNotImplementedError,
    ProviderRequestError,
    ProviderResponseError,
    UnknownProviderError,
)
from providers.llama_provider import LlamaProvider
from providers.models import AIResponse, TokenUsage
from providers.provider_factory import ProviderFactory

__all__ = [
    "AIResponse",
    "AnthropicProviderError",
    "BaseProvider",
    "LlamaProvider",
    "LlamaProviderError",
    "OpenAIProviderError",
    "ProviderConfigurationError",
    "ProviderError",
    "ProviderFactory",
    "ProviderNotImplementedError",
    "ProviderRequestError",
    "ProviderResponseError",
    "TokenUsage",
    "UnknownProviderError",
]

__version__ = "0.2.0"
