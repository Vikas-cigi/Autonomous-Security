# Provider Factory (Architecture V2 — Scaffold)

## Purpose

The **Provider Factory** resolves a provider name to a concrete LLM client
and exposes a uniform `generate(prompt) -> AIResponse` contract.

This package extends the existing `providers/` folder used by V1
`LLMService`. **Legacy `LlamaProvider.chat` / `stream_chat` are preserved**
so current runtime behavior does not change. The factory and `generate`
API are **not** wired into `LLMService`, PromptBuilder, ContextManager, or
FastAPI yet.

## Responsibility

| Layer | Owns |
|-------|------|
| PromptBuilder | Formats `AIContext` → `Prompt` |
| **ProviderFactory** | Selects which backend runs the prompt |
| **BaseProvider** | Talks to one upstream model API |
| LLMService (future) | Orchestrates decision → context → prompt → provider |

## Target Architecture V2 Flow

```
Frontend
    ↓
FastAPI
    ↓
LLMService
    ↓
DecisionEngine
    ↓
ContextManager
    ↓
PromptBuilder
    ↓
ProviderFactory          ← this layer
    ↓
BaseProvider.generate()
    ↓
llama.cpp / OpenAI / Anthropic / …
```

## Package Layout

```
providers/
├── __init__.py
├── provider_factory.py     # get_provider(name) → BaseProvider
├── base_provider.py        # ABC: async generate(prompt) → AIResponse
├── models.py               # AIResponse
├── exceptions.py           # ProviderError hierarchy
├── llama_provider.py       # Working (+ V1 chat/stream_chat)
├── openai_provider.py      # Placeholder
├── anthropic_provider.py   # Placeholder
└── README.md
```

## Provider Lifecycle

1. **Construct** `ProviderFactory()` (or inject a custom registry).
2. **Resolve** `provider = factory.get_provider("llama")`.
3. **Generate** `response = await provider.generate(prompt)`.
4. **Reuse** the same provider instance across requests (stateless HTTP today).
5. **Shutdown** — no shared client pool yet; future app lifespan may own
   `httpx.AsyncClient` cleanup.

Providers registered in the factory are long-lived. The factory does not
create a new instance per `get_provider` call unless you build it that way
via DI.

## Usage (not integrated)

```python
from prompt.models import Prompt, PromptMessage
from providers import ProviderFactory

factory = ProviderFactory()
provider = factory.get_provider("llama")

prompt = Prompt(
    system_prompt="You are Forti AI.",
    messages=[
        PromptMessage(role="system", content="You are Forti AI."),
        PromptMessage(role="user", content="Explain XSS"),
    ],
)

response = await provider.generate(prompt)
print(response.text, response.usage, response.metadata["latency_ms"])
```

### Dependency injection

```python
from providers import ProviderFactory, LlamaProvider
from providers.openai_provider import OpenAIProvider

factory = ProviderFactory(
    providers={
        "llama": LlamaProvider(base_url="http://127.0.0.1:8080"),
        "openai": OpenAIProvider(api_key=None),
    },
    default_provider="llama",
)
```

## How to Add a New Provider

1. Subclass `BaseProvider`.
2. Implement `provider_name` and `async def generate(self, prompt) -> AIResponse`.
3. Add a specific exception in `exceptions.py` if useful.
4. Register it:

```python
class AzureOpenAIProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "azure_openai"

    async def generate(self, prompt):
        ...


factory = ProviderFactory()
factory.register("azure_openai", AzureOpenAIProvider(...))
# or pass it in the constructor `providers={...}` map
```

No changes to `ProviderFactory.get_provider` are required when using
`register` / constructor injection (Open/Closed).

## Implementations

| Provider | Status | Notes |
|----------|--------|-------|
| `LlamaProvider` | **Working** | OpenAI-compatible `/v1/chat/completions` |
| `OpenAIProvider` | Placeholder | Raises `ProviderNotImplementedError` |
| `AnthropicProvider` | Placeholder | Raises `ProviderNotImplementedError` |

### V1 compatibility

`LLMService` still does:

```python
self.provider = LlamaProvider()
await self.provider.chat(messages)
```

That path is unchanged. Do not remove `chat` / `stream_chat` until V2
integration replaces it.

## Exceptions

- `ProviderError` — base
- `UnknownProviderError` — bad factory name
- `ProviderNotImplementedError` — placeholders
- `ProviderRequestError` / `ProviderResponseError` — transport / payload
- `LlamaProviderError` / `OpenAIProviderError` / `AnthropicProviderError`

## Non-Goals (this phase)

- No `LLMService` / PromptBuilder / ContextManager changes
- No FastAPI / frontend integration
- No real OpenAI or Anthropic SDK calls
- No shared connection pool / lifespan hooks yet
