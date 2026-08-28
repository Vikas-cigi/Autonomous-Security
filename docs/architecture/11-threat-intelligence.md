# 11 — Enterprise Threat Intelligence Service

## Purpose

Enrich `SecurityFindingObject` records (joined by `finding_id`) with external and internal threat intelligence. Acts as the intelligence layer between the Evidence Repository and the future Risk Engine.

## Responsibilities

| Owns | Does not own |
|------|----------------|
| CVE / EPSS / KEV / MITRE / IOC catalog | Finding persistence |
| Enrichment envelopes (`ThreatIntelligence`) | Live feed HTTP clients |
| Feed provider abstraction + sync orchestration | Risk scoring (future Risk Engine) |
| Versioning + audit history | REST APIs |

## Inputs

| Name | Type |
|------|------|
| Finding id + CVE / technique / IOC hints | Enrichment request |
| `CVERecord` / IOC / feed metadata | Catalog upserts |
| `FeedSyncRequest` | Provider sync |

## Outputs

| Name | Type |
|------|------|
| `ThreatIntelligence` | Enrichment envelope |
| `CVERecord`, IOCs, feed metadata | Catalog entities |
| `FeedSyncResult` | Sync outcome (often SKIPPED for placeholders) |

## Dependencies

```mermaid
flowchart LR
    Evidence[Evidence Repository] -.->|finding_id / CVE ids| TI[ThreatIntelligenceService]
    TI --> CVE[CVEEnrichmentService]
    TI --> MITRE[MITREMappingService]
    TI --> Exploit[ExploitAnalysisService]
    TI --> IOC[IOCCorrelationService]
    Sync[ThreatFeedSyncService] --> Providers[ThreatFeedProvider registry]
    Providers --> Placeholders[NVD / KEV / MITRE / MISP / … placeholders]
    Sync --> Repos[Repositories]
    TI --> Repos
    Repos --> PG[(PostgreSQL)]
    TI -.-> Risk[Risk Engine future]
```

- **Does not modify** Evidence Repository, Asset Inventory, adapters, normalization, policy, or AI modules
- Enrichment is optional and loosely coupled via `finding_id`

## Threat feed abstraction

`ThreatFeedProvider` is the extension point. Placeholder providers for NVD, CISA KEV, MITRE ATT&CK, MISP, OpenCTI, VirusTotal, AlienVault OTX, and Recorded Future return `FeedSyncStatus.SKIPPED` with no network I/O. Real connectors register into `ThreatFeedProviderRegistry` without changing services.

## Sequence diagram — enrich finding

```mermaid
sequenceDiagram
    participant Caller
    participant Facade as ThreatIntelligenceService
    participant CVE as CVEEnrichmentService
    participant MITRE as MITREMappingService
    participant Exploit as ExploitAnalysisService
    participant Repo as ThreatIntelRepository

    Caller->>Facade: enrich_finding(tenant, finding, cves, techniques)
    Facade->>Repo: get_or_create envelope
    Facade->>CVE: enrich_from_cve_ids
    CVE->>Repo: get_cve / save_intelligence
    Facade->>MITRE: apply_to_intelligence
    Facade->>Exploit: apply
    Facade-->>Caller: ThreatIntelligence
```

## Extension points

- Implement `ThreatFeedProvider.sync` for a real connector
- Register via `ThreatFeedProviderRegistry`
- Swap repository implementations behind ports

## Non-goals

- No REST/GraphQL yet
- No live external API calls in this release
- No changes to existing platform modules

## Source paths

- `backend/threat_intelligence/`
- Package README: `backend/threat_intelligence/README.md`
