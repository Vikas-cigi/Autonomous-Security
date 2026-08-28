# Prompt Builder (Architecture V2 — Scaffold)

## Purpose

The **Prompt Builder** turns an assembled ``AIContext`` into a
provider-ready ``Prompt`` (system text, ordered messages, metadata, and
optional provider hints).

This package is a **standalone scaffold**. It does **not** modify or call
``PromptService``, ``LLMService``, or FastAPI routes. Shipping it now does
**not** change runtime behavior, API contracts, or the frontend.

## Responsibility

| Layer | Owns |
|-------|------|
| DecisionEngine | *What* path to take (CHAT / RAG / TOOL / …) |
| ContextManager | *What information* is available |
| **PromptBuilder** | *How* that information is formatted for the LLM |
| ProviderFactory (future) | *Where* the prompt is sent |

Prompt Builder does **not** retrieve documents, call tools, or talk to
llama.cpp. It only formats.

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
PromptBuilder          ← this package
    ↓
ProviderFactory
    ↓
LLM Provider
```

## Package Layout

```
prompt/
├── __init__.py
├── prompt_builder.py       # Facade: build(context) → Prompt
├── models.py               # Prompt, PromptMessage, ProviderHints
├── README.md
└── templates/
    ├── base_template.py    # BasePromptTemplate ABC
    ├── chat_template.py    # Working implementation
    ├── rag_template.py     # Placeholder
    ├── tool_template.py    # Placeholder
    └── agent_template.py   # Placeholder
```

## Template Architecture

All templates inherit ``BasePromptTemplate``:

```python
class BasePromptTemplate(ABC):
    @property
    def template_name(self) -> str: ...

    def build(self, context: AIContext) -> Prompt: ...
```

| Template | Status | Role |
|----------|--------|------|
| `ChatTemplate` | **Working** | system + history + user message |
| `RAGTemplate` | Placeholder | Will inject `context.documents` |
| `ToolTemplate` | Placeholder | Will format tool schemas / results |
| `AgentTemplate` | Placeholder | Will format plans / scratchpads |

### ChatTemplate behavior

1. Resolve system prompt:
   - `context.system_prompt` if set, else
   - injected override, else
   - `prompts/cyber_system.txt` (same file PromptService reads; **PromptService unchanged**)
2. Append `context.conversation` turns
3. Append current `context.request.message` as `user`
4. Return `Prompt` with metadata

## Usage (not integrated)

```python
from context import ContextManager, ContextRequest
from decision_engine import DecisionEngine
from prompt import PromptBuilder

decision = DecisionEngine().route("Explain XSS remediation")
# In real V2: await ContextManager().build(...)
# For illustration, assume ai_context exists:

builder = PromptBuilder()  # defaults to ChatTemplate
prompt = builder.build(ai_context)

print(prompt.system_prompt)
print(prompt.as_openai_messages())
```

### Dependency injection

```python
from prompt import PromptBuilder
from prompt.templates import ChatTemplate, RAGTemplate

builder = PromptBuilder(
    default_template=ChatTemplate(system_prompt="You are a test assistant."),
    templates={...},  # reserved for future decision routing
)
```

## Future Roadmap

### Near term

1. Wire into `LLMService` behind a feature flag (keep API contracts stable).
2. Pass `Prompt.as_openai_messages()` into ProviderFactory / LlamaProvider.
3. Enable decision-aware template selection using `context.decision`.

### Medium term

4. **RAGTemplate** — cite chunks, enforce grounding instructions.
5. **ToolTemplate** — OpenAI tools / function-call message shapes.
6. **AgentTemplate** — ReAct / plan-and-execute message formats.
7. Populate `provider_hints` (temperature, max_tokens) from config / decision.

### Longer term

8. Token budgeting and history truncation inside templates.
9. Multi-modal message parts (vision) without changing PromptBuilder.
10. A/B template experiments via injected template registries.
11. Deprecate legacy `PromptService` once V2 path is default.

## Non-Goals (this phase)

- No API / FastAPI route changes
- No frontend contract changes
- No `PromptService` / `LLMService` modifications
- No live integration into the request path
