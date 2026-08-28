"""
Enterprise Simulation Engine
============================

Performs a **dry-run simulation** of a ``RemediationPlan`` before any execution.
Predicts impact without infrastructure changes or external API calls.

**Pipeline:** Remediation Planner → **Simulation Engine** → Approval Engine

## Non-goals

- No REST APIs
- No infrastructure mutation
- No external adapter / scanner API execution
- Does not modify existing platform modules
- Does not replace canonical ``models.simulation`` (exports into it)

## Quick start

```python
from uuid import uuid4
from simulation_engine import SimulationEngineContainer, SimulationRequest
from simulation_engine.domain.inputs import (
    RemediationPlanSnapshot,
    PlanStepSnapshot,
    RiskSimulationInput,
    AssetSimulationInput,
    PolicySimulationInput,
)

container = SimulationEngineContainer.from_url(
    "sqlite+pysqlite:///:memory:",
    create_tables=True,
)

plan_id, tenant_id, finding_id, decision_id, asset_id = (
    uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
)
step_id = uuid4()
request = SimulationRequest(
    plan=RemediationPlanSnapshot(
        plan_id=plan_id,
        tenant_id=tenant_id,
        finding_id=finding_id,
        decision_id=decision_id,
        asset_id=asset_id,
        execution_type="package_upgrade",
        summary="Upgrade OpenSSH",
        steps=[
            PlanStepSnapshot(
                step_id=step_id,
                sequence=1,
                action="Upgrade package",
                target="prod-web-01",
                estimated_duration_seconds=120,
            )
        ],
        planned_downtime_seconds=120,
        change_window_required=True,
    ),
    risk=RiskSimulationInput(enterprise_risk_score=88.0, risk_level="high"),
    asset=AssetSimulationInput(
        asset_id=asset_id,
        hostname="prod-web-01",
        environment="production",
        criticality=0.9,
    ),
    policy=PolicySimulationInput(policy_version="1.0.0"),
)

with container.session() as session:
    svc = container.build(session)
    result = svc.engine.simulate(request)
    print(result.safe_to_execute, result.outcome, result.summary)
    print(result.to_canonical_simulation_object().status)
```

## Layout

```
simulation_engine/
  domain/         # models, inputs, history, enums
  interfaces/     # simulation + audit repository ports
  persistence/    # SQLAlchemy ORM (se_*) + Postgres repos
  services/       # blast / deps / rollback / policy / impact / facade
  query/          # filters + pagination
  di/             # composition root
```

## Outputs

- Safe To Execute (Yes/No)
- Estimated Blast Radius / Downtime
- Rollback Possible
- Risk Reduction
- Affected Assets
- Execution Warnings / Policy Violations
- Confidence Score
- Human-readable Summary
"""
