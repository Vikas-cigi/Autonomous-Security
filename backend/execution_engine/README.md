"""
Enterprise Execution Engine
===========================

Orchestrates **approved** remediation plan execution after Approval Engine
and before Verification Engine.

Never evaluates policy, recalculates trust/risk, invokes AI, or modifies plans.

**Pipeline:** Approval Engine → **Execution Engine** → Verification Engine

## Non-goals

- No REST APIs
- No Policy Engine evaluation
- No Trust / Risk recalculation
- No AI / LLM calls
- Does not modify RemediationPlan
- Does not modify existing platform modules

## Quick start

```python
from uuid import uuid4
from execution_engine import ExecutionEngineContainer, ExecutionRequest
from execution_engine.domain.inputs import (
    ExecutionAuthorizationInput,
    ApprovalDecisionInput,
    DecisionExecutionInput,
    RemediationPlanInput,
    PlanStepInput,
    SimulationExecutionInput,
)

container = ExecutionEngineContainer.from_url(
    "sqlite+pysqlite:///:memory:",
    create_tables=True,
)

ids = {k: uuid4() for k in (
    "auth", "approval", "plan", "tenant", "finding", "decision", "sim", "step"
)}
request = ExecutionRequest(
    authorization=ExecutionAuthorizationInput(
        authorized=True,
        authorization_id=ids["auth"],
        approval_id=ids["approval"],
        tenant_id=ids["tenant"],
        plan_id=ids["plan"],
        simulation_id=ids["sim"],
        reason="approved",
    ),
    approval=ApprovalDecisionInput(
        approval_id=ids["approval"],
        state="approved",
        decided_by="sec-manager",
    ),
    decision=DecisionExecutionInput(
        decision_id=ids["decision"],
        finding_id=ids["finding"],
        tenant_id=ids["tenant"],
        decision="remediate",
    ),
    plan=RemediationPlanInput(
        plan_id=ids["plan"],
        execution_type="package_upgrade",
        summary="Upgrade OpenSSH",
        steps=[
            PlanStepInput(
                step_id=ids["step"],
                sequence=1,
                action="Upgrade package",
                target="prod-web-01",
            )
        ],
    ),
    simulation=SimulationExecutionInput(
        simulation_id=ids["sim"],
        outcome="safe",
        safe_to_execute=True,
        confidence_score=0.9,
    ),
)

with container.session() as session:
    svc = container.build(session)
    result = svc.engine.execute(request)
    print(result.status, result.summary)
    print(result.verification_request)
```

## Layout

```
execution_engine/
  domain/         # models, inputs, history, enums
  interfaces/     # execution / history / audit / rollback / step adapter ports
  adapters/       # DeterministicRecordingAdapter (default; swap for real infra)
  persistence/    # SQLAlchemy ORM (ee_*) + Postgres repos
  services/       # validation / workflow / coordinator / steps / rollback / facade
  query/          # filters + pagination
  di/             # composition root
```

## Infrastructure integration

Inject a custom ``StepInfrastructureAdapter`` into ``ExecutionEngineContainer``
to call real cloud/config providers without changing orchestration business logic.
"""
