# 17 — Enterprise Simulation Engine

## Purpose

Perform a **dry-run simulation** of a `RemediationPlan` before Approval Engine / execution. Predict blast radius, downtime, rollback feasibility, policy conflicts, and risk reduction **without** changing infrastructure or calling external APIs.

## Responsibilities

| Owns | Does not own |
|------|----------------|
| Deterministic dry-run analysis | Live remediation execution |
| Blast radius / dependency / rollback / policy impact | Trust / Risk scoring |
| Versioned multi-tenant simulation persistence | REST APIs |
| Canonical `SimulationObject` export | Approval workflow |

## Inputs

| Name | Type |
|------|------|
| `SimulationRequest` | Snapshots of RemediationPlan, Risk, Asset, TI, Policy |

## Outputs

| Name | Type |
|------|------|
| `SimulationResult` | Envelope (outcome, safe_to_execute, impact, warnings, summary) |
| Canonical export | `to_canonical_simulation_object()` → `models.simulation.SimulationObject` |

## Dependencies

```mermaid
flowchart LR
    Planner[Remediation Planner] -.->|RemediationPlan snapshot| SE[SimulationEngineService]
    Risk[Risk Engine] -.->|snapshot| SE
    Assets[Asset Inventory] -.->|snapshot| SE
    TI[Threat Intelligence] -.->|snapshot| SE
    Policy[Policy constraints] -.->|snapshot| SE
    SE --> Blast[BlastRadiusService]
    SE --> Dep[DependencyAnalysisService]
    SE --> Roll[RollbackAnalysisService]
    SE --> Pol[PolicySimulationService]
    SE --> Impact[ImpactAssessmentService]
    SE --> Repos[Simulation / Audit Repos]
    Repos --> PG[(PostgreSQL)]
    SE -.-> Approval[Approval Engine future]
```

- **Does not modify** existing modules
- Callers assemble snapshots; engine never reaches into sibling ORM tables

## Sequence diagram — simulate

```mermaid
sequenceDiagram
    participant Caller
    participant Facade as SimulationEngineService
    participant Impact as ImpactAssessmentService
    participant Blast as BlastRadiusService
    participant Dep as DependencyAnalysisService
    participant Roll as RollbackAnalysisService
    participant Pol as PolicySimulationService
    participant Repo as SimulationRepository

    Caller->>Facade: simulate(SimulationRequest)
    Facade->>Impact: assess(request)
    Impact->>Blast: estimate
    Impact->>Dep: analyze
    Impact->>Roll: assess
    Impact->>Pol: evaluate
    Impact-->>Facade: ImpactAssessment + steps + warnings
    Facade->>Facade: decide(outcome, safe, confidence)
    Facade->>Repo: save(SimulationResult)
    Facade-->>Caller: SimulationResult
```

## Determinism

- Fixed formulas for blast radius, downtime buffer, risk reduction, confidence
- No randomness, AI, or network I/O
- `algorithm_version` stamped on every result

## Design goals

- No infrastructure changes
- No external API execution
- Fully auditable + versioned
- Multi-tenant isolation on all queries

## Non-goals

- No REST/GraphQL
- No live execution / adapter calls
- No mutation of existing modules

## Source paths

- `backend/simulation_engine/`
- Package README: `backend/simulation_engine/README.md`
