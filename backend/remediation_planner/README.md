"""
Enterprise Remediation Planner
==============================

Converts an approved ``DecisionObject`` into a structured, executable
``RemediationPlan``. Does **not** execute infrastructure changes and makes
**no AI calls**.

**Pipeline:** Decision Service → **Remediation Planner** → Simulation Engine

## Non-goals

- No REST APIs
- No AI / LLM
- No execution / infrastructure mutation
- Does not modify existing platform modules
- Does not replace canonical ``models.remediation`` (exports into it)

## Quick start

```python
from uuid import uuid4
from models.common import ActorReference
from models.enums import DecisionAction, Priority, RecommendedAction
from remediation_planner import RemediationPlannerContainer, RemediationPlanRequest
from remediation_planner.domain.inputs import (
    DecisionPlanInput, FindingPlanInput, RiskPlanInput,
)

container = RemediationPlannerContainer.from_url(
    "sqlite+pysqlite:///:memory:",
    create_tables=True,
)

finding_id, tenant_id, asset_id, decision_id = uuid4(), uuid4(), uuid4(), uuid4()
request = RemediationPlanRequest(
    decision=DecisionPlanInput(
        decision_id=decision_id,
        finding_id=finding_id,
        tenant_id=tenant_id,
        decision=DecisionAction.REMEDIATE,
        recommended_action=RecommendedAction.APPLY_PATCH,
        priority=Priority.P1,
        confidence=0.9,
        reason="Patch critical CVE",
        policy_version="1.0.0",
        owner=ActorReference(
            actor_id=uuid4(), display_name="SOC", actor_type="user"
        ),
    ),
    finding=FindingPlanInput(
        finding_id=finding_id,
        tenant_id=tenant_id,
        asset_id=asset_id,
        title="CVE finding",
        cve_ids=["CVE-2024-1"],
        package_name="openssl",
        fixed_version="3.0.14",
    ),
    risk=RiskPlanInput(enterprise_risk_score=88.0, risk_level="high"),
)

with container.session() as session:
    svc = container.build(session)
    plan = svc.planner.plan(request)
    print(plan.execution_type, plan.estimated_duration.human_summary)
    print(plan.to_canonical_plan().summary)
```

## Layout

```
remediation_planner/
  domain/         # models, inputs, catalog, history, enums
  interfaces/     # plan + history repository ports
  persistence/    # SQLAlchemy ORM (rp_*) + Postgres repos
  services/       # generation / deps / rollback / impact / cost / facade
  query/          # filters + pagination
  di/             # composition root
```

## Execution types

Patch, Configuration Change, Secret Rotation, Firewall Update,
IAM Policy Change, Network Isolation, Container Update, Package Upgrade,
Manual Investigation

## Architecture doc

See ``docs/architecture/15-remediation-planner.md``.
"""
