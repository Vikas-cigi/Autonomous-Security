# 20 — Enterprise Verification Engine

## Purpose

Validate whether **approved remediation** was successfully executed and whether the original security finding has been resolved. Runs after Execution Engine and before Reporting & Analytics.

## Responsibilities

| Owns | Does not own |
|------|----------------|
| Post-remediation validation + check plan | Remediation execution |
| Evidence before/after comparison | Risk / trust recalculation |
| Rescan result interpretation (caller-provided) | Invoking scanners or AI |
| Closure / reopen / escalate recommendations | Approval or plan mutation |
| Versioned multi-tenant audit history | REST APIs |

## Inputs

| Name | Type |
|------|------|
| `VerificationRequest` | Snapshots: Execution, Plan, Decision, Finding, Evidence, Asset, Risk scores, Org policy, Rescan |

## Outputs

| Name | Type |
|------|------|
| `VerificationResult` | Status, checks, comparison, finding disposition, timeline, metrics, events |
| `VerificationReport` / `VerificationSummary` | Operator-facing artifacts |
| Closure recommendation | Close / Reopen / Escalate / Manual / Additional remediation |
| Canonical export | `to_canonical_verification_object()` → `models.verification.VerificationObject` |

## Dependencies

```mermaid
flowchart LR
    Exec[Execution Engine] -.->|execution + plan snapshots| VE[VerificationEngineService]
    EvidenceRepo[Evidence Repository] -.->|evidence snapshots| VE
    Assets[Asset Inventory] -.->|asset snapshot| VE
    Risk[Risk Engine] -.->|pre/post scores only| VE
    VE --> Valid[VerificationValidationService]
    VE --> WF[VerificationWorkflowService]
    VE --> Cmp[VerificationComparisonService]
    VE --> Ev[VerificationEvidenceService]
    VE --> Checks[VerificationCheckRunner]
    VE --> Report[VerificationReportingService]
    VE --> Repos[Verification / Evidence / Audit Repos]
    Repos --> PG[(PostgreSQL)]
    VE -.-> Reporting[Reporting and Analytics future]
```

- **Does not modify** existing modules
- Risk reduction is **confirmed** from caller-provided scores, never recalculated
- Rescans are **interpreted**, never initiated against live scanners inside this package

## Sequence diagram — verify

```mermaid
sequenceDiagram
    participant Caller
    participant Facade as VerificationEngineService
    participant Valid as VerificationValidationService
    participant Ev as VerificationEvidenceService
    participant Cmp as VerificationComparisonService
    participant Checks as VerificationCheckRunner
    participant WF as VerificationWorkflowService
    participant Repo as VerificationRepository

    Caller->>Facade: verify(VerificationRequest)
    Facade->>Valid: validate_request
    Facade->>Repo: save(pending)
    Facade->>Ev: collect + persist evidence
    Facade->>Cmp: compare pre/post + risk snapshots
    Facade->>Checks: run_all(plan)
    Facade->>WF: resolve_outcome
    Facade->>Repo: save(terminal)
    Facade-->>Caller: VerificationResult
```

## Verification states

Pending → Running → Verified | Failed | Reopened | Escalated | Cancelled | Completed

## Design goals

- Deterministic, auditable, multi-tenant
- Never execute remediation / never AI / never risk recalculation
- Extensible check plan via org policy knobs

## Non-goals

- No REST/GraphQL
- No live scanner or cloud SDK coupling in core
- No mutation of existing modules

## Source paths

- `backend/verification_engine/`
- Package README: `backend/verification_engine/README.md`
