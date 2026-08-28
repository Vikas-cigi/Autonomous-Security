"""
Enterprise AI Harness
=====================

Centralized orchestration for every AI interaction in Xolaris.

Wraps Architecture V2:

- Context Manager
- Prompt Builder
- Provider Factory

Adds validation, retries, provider fallback, timeout handling, reflection,
confidence scoring, usage/cost tracking, and auditability.

**No cybersecurity business logic.** No REST APIs.

## Quick start

```python
import asyncio
from uuid import uuid4
from ai_harness import AIHarnessContainer, AIRequest

container = AIHarnessContainer.from_url(
    "sqlite+pysqlite:///:memory:",
    create_tables=True,
)

request = AIRequest(
    tenant_id=uuid4(),
    message='Return JSON: {"ok": true}',
    expect_json=True,
    required_json_keys=["ok"],
    provider_name="llama",
    fallback_providers=["openai"],
    max_retries=2,
    timeout_seconds=30,
)

async def main():
    with container.session() as session:
        svc = container.build(session)
        result = await svc.harness.run(request)
        print(result.status, result.response.text if result.response else None)

asyncio.run(main())
```

## Layout

```
ai_harness/
  domain/         # AIRequest/Response/Execution models
  interfaces/     # execution + audit repository ports
  persistence/    # SQLAlchemy ORM (ah_*) + Postgres repos
  services/       # harness facade + execution/validation/reflection/...
  query/          # filters + pagination
  di/             # composition root
```

## Architecture doc

See ``docs/architecture/16-ai-harness.md``.
"""
