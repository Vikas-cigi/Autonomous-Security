"""
Enterprise Approval Engine
==========================

Governs remediation **execution authorization** after simulation and before
execution. Never executes remediation, never calls AI, and never mutates
plans or risk calculations.

**Pipeline:** Simulation Engine → **Approval Engine** → Execution Engine

## Non-goals

- No REST APIs
- No infrastructure / adapter execution
- No AI / LLM calls
- Does not modify existing platform modules
- Does not replace canonical ``ApprovalRecord`` (exports into it)

## Quick start

```python
from uuid import uuid4
from approval_engine import ApprovalEngineContainer, ApprovalSubmitRequest
from approval_engine.domain.inputs import (
    DecisionApprovalInput,
    PlanApprovalInput,
    SimulationApprovalInput,
    RiskApprovalInput,
    AssetApprovalInput,
    OrgPolicyApprovalInput,
)

container = ApprovalEngineContainer.from_url(
    "sqlite+pysqlite:///:memory:",
    create_tables=True,
)

ids = {k: uuid4() for k in ("plan", "tenant", "finding", "decision", "sim", "asset")}
request = ApprovalSubmitRequest(
    decision=DecisionApprovalInput(
        decision_id=ids["decision"],
        finding_id=ids["finding"],
        tenant_id=ids["tenant"],
        decision="remediate",
    ),
    plan=PlanApprovalInput(
        plan_id=ids["plan"],
        execution_type="package_upgrade",
        summary="Upgrade OpenSSH",
    ),
    simulation=SimulationApprovalInput(
        simulation_id=ids["sim"],
        outcome="conditional",
        safe_to_execute=True,
        confidence_score=0.85,
    ),
    risk=RiskApprovalInput(enterprise_risk_score=92.0, risk_level="critical"),
    asset=AssetApprovalInput(
        asset_id=ids["asset"],
        environment="production",
        criticality=0.9,
    ),
    org_policy=OrgPolicyApprovalInput(auto_approve_enabled=False),
)

with container.session() as session:
    svc = container.build(session)
    approval = svc.engine.submit(request)
    print(approval.state, approval.assigned_approvers)
    print(approval.to_canonical_approval_record().status)
```

## Layout

```
approval_engine/
  domain/         # models, inputs, policy catalog, history, enums
  interfaces/     # approval / policy / workflow / audit ports
  persistence/    # SQLAlchemy ORM (ae_*) + Postgres repos
  services/       # policy / workflow / routing / validation / audit / facade
  query/          # filters + pagination
  di/             # composition root
```

## Outputs

- ApprovalDecision / ExecutionAuthorization
- Assigned approvers + multi-stage workflow
- Approval timeline / escalation status
- Versioned history + audit records
"""
