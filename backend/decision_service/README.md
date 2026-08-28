"""
Enterprise Decision Service
===========================

Orchestration layer that prepares intelligence for AI-assisted cybersecurity
decisions and emits a canonical ``DecisionObject``.

**Pipeline position:** after Risk Engine → **Decision Service** → Remediation Planner.

Distinct from ``decision_engine`` (Architecture V2 intent routing: CHAT/TOOL/RAG).

## Non-goals

- No REST APIs yet
- No duplicated Trust / Risk / TI / Evidence scoring
- No direct scanner interaction
- Does not modify existing platform modules

## Quick start (deterministic, no AI)

```python
import asyncio
from uuid import uuid4
from models.common import ActorReference
from decision_service import DecisionServiceContainer, DecisionRequest
from decision_service.domain.inputs import (
    FindingSnapshot, TrustSnapshot, RiskSnapshot, PolicySnapshot,
)

container = DecisionServiceContainer.from_url(
    "postgresql+psycopg://user:pass@localhost:5432/xolaris",
    create_tables=True,
    enable_ai_stack=False,
)

finding_id, tenant_id, asset_id = uuid4(), uuid4(), uuid4()
request = DecisionRequest(
    finding=FindingSnapshot(
        finding_id=finding_id, tenant_id=tenant_id, asset_id=asset_id,
        title="Open SSH", severity="high",
    ),
    trust=TrustSnapshot(trust_score=80.0, trust_level="high"),
    risk=RiskSnapshot(
        enterprise_risk_score=75.0, risk_level="high", priority="p2",
    ),
    owner=ActorReference(
        actor_id=uuid4(), display_name="SOC Analyst", actor_type="user",
    ),
    policy=PolicySnapshot(precomputed_verdict="allow"),
    invoke_ai=False,
)

async def main():
    with container.session() as session:
        svc = container.build(session)
        response = await svc.decision.decide(request)
        print(response.decision_object.decision, response.explanation.summary)

asyncio.run(main())
```

## With AI stack

Inject Architecture V2 Context Manager → Prompt Builder → Provider Factory
via ``AIStackGateway`` (default when ``enable_ai_stack=True``), or supply a
custom ``AIDecisionGateway``.

## Layout

```
decision_service/
  domain/         # models, inputs, mapping, history, enums
  interfaces/     # Decision / Audit repos + AI gateway port
  adapters/       # AIStackGateway (consumes V2 modules)
  persistence/    # SQLAlchemy ORM (ds_*) + Postgres repos
  services/       # orchestration facade + assemblers/validators
  query/          # filters + pagination
  di/             # composition root
```

## Decision types

| Type | Canonical DecisionAction |
|------|--------------------------|
| remediate | remediate |
| ignore | no_action |
| escalate | escalate |
| investigate | investigate |
| monitor | monitor |

## Architecture doc

See ``docs/architecture/14-decision-service.md``.
"""
