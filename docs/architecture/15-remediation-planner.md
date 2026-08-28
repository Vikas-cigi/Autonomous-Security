# 15 — Enterprise Remediation Planner

## Purpose

Convert an approved `DecisionObject` into a structured, deterministic **RemediationPlan** that can later be simulated, approved, executed, and verified. The planner **does not execute** infrastructure changes and makes **no AI calls**.

## Responsibilities

| Owns | Does not own |
|------|----------------|
| Plan generation (steps, tasks, validations) | Trust / Risk / Decision scoring |
| Dependency graph + rollback strategy | Simulation execution |
| Impact / duration / cost / change-window estimates | Live infrastructure changes |
| Versioned multi-tenant plan persistence | REST APIs |

## Inputs

| Name | Type |
|------|------|
| `RemediationPlanRequest` | Snapshots of Decision, Finding, Risk, Asset, TI, Policy |

## Outputs

| Name | Type |
|------|------|
| `RemediationPlan` | Planner envelope (steps, tasks, rollback, estimates) |
| Canonical exports | `to_canonical_plan()` / `to_canonical_rollback()` → `models.remediation` |

## Dependencies

```mermaid
flowchart LR
    Decision[Decision Service] -.->|DecisionObject snapshot| RP[RemediationPlannerService]
    Finding[SecurityFindingObject] -.->|snapshot| RP
    Risk[Risk Engine] -.->|snapshot| RP
    Assets[Asset Inventory] -.->|snapshot| RP
    TI[Threat Intelligence] -.->|snapshot| RP
    Policy[Policy constraints] -.->|snapshot| RP
    RP --> Gen[PlanGenerationService]
    RP --> Dep[DependencyResolutionService]
    RP --> Roll[RollbackPlanningService]
    RP --> Impact[ImpactAnalysisService]
    RP --> Cost[CostEstimationService]
    RP --> Repos[Plan / History Repos]
    Repos --> PG[(PostgreSQL)]
    RP -.-> Sim[Simulation Engine]
```

- **Does not modify** existing modules
- Callers assemble snapshots; planner never reaches into sibling ORM tables

## Sequence diagram — plan

```mermaid
sequenceDiagram
    participant Caller
    participant Facade as RemediationPlannerService
    participant Gen as PlanGenerationService
    participant Dep as DependencyResolutionService
    participant Roll as RollbackPlanningService
    participant Impact as ImpactAnalysisService
    participant Cost as CostEstimationService
    participant Repo as RemediationPlanRepository

    Caller->>Facade: plan(RemediationPlanRequest)
    Facade->>Gen: generate(steps/tasks/validations)
    Facade->>Dep: resolve(dependency graph)
    Facade->>Roll: build(rollback plan)
    Facade->>Impact: analyze(impact/duration/approvals/window)
    Facade->>Cost: estimate(cost)
    Facade->>Repo: save(RemediationPlan)
    Facade-->>Caller: RemediationPlan
```

## Determinism

- Fixed execution-type selection + step templates
- No randomness, AI, or network I/O
- `algorithm_version` stamped on every plan

## Non-goals

- No REST/GraphQL
- No AI/LLM
- No infrastructure execution
- No mutation of existing modules

## Source paths

- `backend/remediation_planner/`
- Package README: `backend/remediation_planner/README.md`
