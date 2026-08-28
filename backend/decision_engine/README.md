# Decision Engine (Architecture V2 — Scaffold)

## Purpose

The **Decision Engine** will become the routing entry point for all AI
requests in Architecture V2. It decides *how* a message should be handled
(chat, tool use, RAG, memory, agent, or unknown) **before** context
assembly, prompt building, or provider selection.

This package is a **standalone scaffold**. It is **not** imported by
`LLMService`, FastAPI routers, or any other live module yet. Shipping it
now does **not** change runtime behavior, API contracts, or the frontend.

## Target Architecture V2 Flow

```
Frontend
    ↓
FastAPI
    ↓
LLMService
    ↓
DecisionEngine          ← this package
    ↓
ContextManager
    ↓
PromptBuilder
    ↓
ProviderFactory
    ↓
LLM Provider
```

## Package Layout

| File | Role |
|------|------|
| `models.py` | `DecisionType` enum and `DecisionResult` model |
| `intent_router.py` | Intent classification (`detect_intent`) |
| `decision_engine.py` | Facade (`route`) that delegates to `IntentRouter` |
| `__init__.py` | Stable public exports |

## Current Behavior (Phase 0)

`IntentRouter.detect_intent(message)` always returns:

- `decision_type`: `CHAT`
- `confidence`: `1.0`
- `reason`: scaffold passthrough explanation
- `metadata`: router name, message length, strategy tag

No AI / NLP classification is performed yet.

## Usage (not integrated)

```python
from decision_engine import DecisionEngine, DecisionType

engine = DecisionEngine()
result = engine.route("How do I mitigate SQL injection?")

assert result.decision_type is DecisionType.CHAT
assert result.confidence == 1.0
```

### Unit testing via dependency injection

```python
from decision_engine import DecisionEngine, DecisionResult, DecisionType
from decision_engine.intent_router import IntentRouter

class FakeRouter(IntentRouter):
    def detect_intent(self, message: str) -> DecisionResult:
        return DecisionResult(
            decision_type=DecisionType.RAG,
            confidence=0.9,
            reason="test double",
            metadata={"fixture": True},
        )

engine = DecisionEngine(intent_router=FakeRouter())
assert engine.route("docs?").decision_type is DecisionType.RAG
```

## What Comes Next (not in this change)

1. Wire `DecisionEngine` into `LLMService` behind a feature flag.
2. Replace passthrough intent detection with real classifiers.
3. Branch on `DecisionType` into ContextManager / tools / RAG / agents.
4. Keep FastAPI request/response shapes unchanged for the frontend.

## Non-Goals (this phase)

- No API endpoint changes
- No frontend contract changes
- No `LLMService` modifications
- No provider / prompt / memory integration
