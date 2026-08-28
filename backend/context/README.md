# Context Manager (Architecture V2 — Refined Scaffold)

## Purpose

The **Context Manager** assembles everything the LLM needs for a single
request: conversation history, long-term memory, RAG documents, user
profile, tool results, and routing metadata from the Decision Engine.

This package is a **standalone scaffold**. It is **not** imported by
`LLMService`, FastAPI routers, or PromptService. Shipping it now does
**not** change runtime behavior, API contracts, or the frontend.

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
ContextManager          ← this package (orchestrator only)
    ↓
PromptBuilder
    ↓
ProviderFactory
    ↓
LLM Provider
```

## Package Layout

```
context/
├── __init__.py
├── context_manager.py          # Orchestrator only
├── models.py                   # AIContext (+ version), ContextRequest, …
├── README.md
└── builders/
    ├── base_builder.py         # BaseContextBuilder (ABC, async)
    ├── conversation_builder.py
    ├── memory_builder.py
    ├── rag_builder.py
    ├── profile_builder.py
    └── tool_builder.py
```

## Why `BaseContextBuilder` Exists

- **Uniform contract** — every builder exposes `async def build(request, decision)`
  and a `field_name` property.
- **Liskov / Dependency Inversion** — `ContextManager` depends on the
  abstraction, not concrete Redis/Qdrant/HTTP clients.
- **Open/Closed** — new builders subclass the base and join the pipeline;
  the orchestrator does not need edits for each specialty.

## Why Builders Are Async

Future builders will perform I/O against:

- Redis (session / cache)
- Qdrant (vector retrieval)
- PostgreSQL (profiles, audit)
- HTTP APIs (threat intel, enrichment)
- MCP servers (external tools)

An `async def build(...)` contract lets those implementations await without
blocking the event loop. Phase-0 builders are async even when they return
empty defaults so the interface does not change later.

**Not implemented in this phase:** Redis, Qdrant, LangChain, MCP, Agents.

## Why ContextManager Contains No Business Logic

`ContextManager` only:

1. Calls builders
2. Collects results
3. Assembles `AIContext`
4. Returns `AIContext`

Retrieval rules, ranking, prompt policy, and domain shaping live **inside
builders**. Request coercion lives on `ContextRequest.coerce`. Keeping the
orchestrator thin prevents a god-object and makes parallel execution a
localized change inside `_collect_builder_results`.

## Parallel Execution (Prepared, Not Enabled)

Builders run **sequentially** today:

```python
value = await builder.build(request, decision)
```

`_collect_builder_results` documents the future swap to:

```python
await asyncio.gather(*(b.build(request, decision) for b in self._builders))
```

No `asyncio.gather` is used yet.

## AIContext Fields

| Field | Phase 0 source |
|-------|----------------|
| `version` | `"1.0"` |
| `request` | `ContextRequest` (via `coerce` if needed) |
| `conversation` | `ConversationBuilder` ← `MemoryService.get_history` |
| `memory` | `MemoryBuilder` → empty |
| `documents` | `RAGBuilder` → `[]` |
| `profile` | `ProfileBuilder` → empty |
| `tool_results` | `ToolBuilder` → `[]` |
| `system_prompt` | `None` |
| `metadata` | `builder_order`, `extensions`, … |
| `decision` | Passed-in `DecisionResult` |

## Adding Future Builders Without Changing ContextManager

Implement `BaseContextBuilder`, set `field_name`, inject into the pipeline:

```python
class SemanticMemoryBuilder(BaseContextBuilder):
    @property
    def field_name(self) -> str:
        return "semantic_memory"  # → metadata["extensions"]

    async def build(self, request, decision):
        return {"embeddings_refs": []}


class ThreatIntelBuilder(BaseContextBuilder):
    @property
    def field_name(self) -> str:
        return "threat_intel"

    async def build(self, request, decision):
        return {"iocs": []}


class VisionBuilder(BaseContextBuilder):
    @property
    def field_name(self) -> str:
        return "vision"

    async def build(self, request, decision):
        return {"captions": []}


class MCPBuilder(BaseContextBuilder):
    @property
    def field_name(self) -> str:
        return "mcp"

    async def build(self, request, decision):
        return {"tool_snapshots": []}


manager = ContextManager(
    builders=[
        *ContextManager.default_builders(),
        SemanticMemoryBuilder(),
        ThreatIntelBuilder(),
        VisionBuilder(),
        MCPBuilder(),
    ]
)
```

- Core keys (`conversation`, `memory`, `documents`, `profile`,
  `tool_results`, `system_prompt`) map onto `AIContext` fields.
- Any other `field_name` is stored under `metadata["extensions"]`
  without touching `ContextManager`.

## Usage (not integrated)

```python
import asyncio
from context import ContextManager, ContextRequest
from decision_engine import DecisionEngine

async def main():
    decision = DecisionEngine().route("Explain XSS remediation")
    manager = ContextManager()
    ai_context = await manager.build(
        ContextRequest(message="Explain XSS remediation", session_id="abc"),
        decision,
    )
    assert ai_context.version == "1.0"

asyncio.run(main())
```

## Unit Testing via Dependency Injection

```python
import asyncio
from context import ContextManager
from context.builders import ConversationBuilder, RAGBuilder, BaseContextBuilder
from context.models import ContextRequest, DocumentChunk

class FakeMemory:
    def get_history(self, session_id: str):
        return [{"role": "user", "content": "hi"}]

class StubRAG(RAGBuilder):
    async def build(self, request, decision):
        return [DocumentChunk(id="1", content="cve notes", score=0.9)]

manager = ContextManager(
    builders=[
        ConversationBuilder(memory_service=FakeMemory()),
        StubRAG(),
    ]
)
```

## Non-Goals (this phase)

- No API / FastAPI route changes
- No frontend contract changes
- No `LLMService` / `PromptService` / `MemoryService` modifications
- No Redis, Qdrant, LangChain, MCP, or Agents
- No live integration into the request path
- No `asyncio.gather` yet
