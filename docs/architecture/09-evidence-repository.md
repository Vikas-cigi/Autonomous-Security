# 09 — Enterprise Evidence Repository

## Purpose

Persist and query canonical `SecurityFindingObject` / `EvidenceObject` records with versioning, audit history, deduplication, cross-scanner correlation, and strict multi-tenant isolation.

## Responsibilities

| Owns | Does not own |
|------|----------------|
| Finding/evidence storage | Scanner execution |
| Versions + history + audit log | HTTP APIs (future) |
| Dedup / correlation / search | Policy evaluation |
| Lifecycle mapping onto `FindingStatus` | Creating findings from raw JSON |

## Inputs

| Name | Type |
|------|------|
| `SecurityFindingObject` | Canonical finding |
| `EvidenceObject` | Canonical evidence |
| `FindingSearchFilter` + `PageRequest` | Query |

## Outputs

| Name | Type |
|------|------|
| Persisted findings/evidence | Canonical models |
| `FindingVersion` / `EvidenceVersion` | Snapshots |
| `FindingHistory` | Lifecycle/audit trail |
| `Page[SecurityFindingObject]` | Search results |
| `DeduplicationResult` / `CorrelationGroup` | Service outcomes |

## Dependencies

```mermaid
flowchart TB
    Norm[NormalizationService] -->|SecurityFindingObject| Dedup[DeduplicationService]
    Dedup --> Repo[EvidenceRepository]
    Corr[CorrelationService] --> Repo
    Search[SearchService] --> Repo
    Repo --> PG[(PostgreSQL)]
    Repo --> Audit[AuditLogger]
```

- **Imports** canonical models from `models/` (read-only usage)
- **Does not modify** adapters, normalization, policy, or AI modules

## Lifecycle mapping

| Product lifecycle | Canonical `FindingStatus` examples |
|-------------------|--------------------------------------|
| Open | `new`, `triaged`, `reopened` |
| In Progress | `in_review`, `remediating`, `verifying`, … |
| Resolved | `resolved` |
| Accepted Risk | `accepted_risk` |
| False Positive | `false_positive`, `suppressed` |

## Sequence diagram — ingest + dedup

```mermaid
sequenceDiagram
    participant Pipe as Ingest Pipeline
    participant Dedup as DeduplicationService
    participant Repo as PostgresEvidenceRepository
    participant DB as PostgreSQL

    Pipe->>Dedup: ingest(finding)
    Dedup->>Repo: find_by_fingerprint(tenant, fp)
    alt miss
        Dedup->>Repo: save_finding (v1 + history)
    else hit
        Dedup->>Dedup: merge evidence/CVEs
        Dedup->>Repo: save_finding (vN + history)
    end
    Repo->>DB: INSERT/UPDATE + versions
    Dedup-->>Pipe: DeduplicationResult
```

## Sequence diagram — search

```mermaid
sequenceDiagram
    participant Caller
    participant Search as SearchService
    participant Repo as EvidenceRepository
    participant Audit as AuditLogger

    Caller->>Search: search(filter, page)
    Note over Search: tenant_id required
    Search->>Repo: search_findings
    Repo->>Audit: log SEARCHED
    Repo-->>Search: Page[SecurityFindingObject]
    Search-->>Caller: Page
```

## Extension points

- Swap `EvidenceRepository` implementation (e.g. partitioned shards)
- Add read models / projections without changing canonical payloads
- Expose FastAPI routers later using `SearchService` + DI container

## Non-goals

- No REST/GraphQL in this module yet
- No changes to existing platform modules

## Source paths

- `backend/evidence_repository/`
- Package README: `backend/evidence_repository/README.md`
