"""
Enterprise Evidence Repository
==============================

Central source of truth for normalized ``SecurityFindingObject`` and
``EvidenceObject`` records.

## Responsibilities

- Persist findings & evidence (PostgreSQL-compatible SQLAlchemy 2.x)
- Version findings and evidence (immutable snapshots)
- Append-only finding history + repository audit log
- Deduplicate by fingerprint
- Correlate across scanners
- Search with tenant isolation, pagination, and filters
- Track lifecycle: Open / In Progress / Resolved / Accepted Risk / False Positive

## Non-goals (this package)

- No HTTP APIs yet
- Does not modify Normalization, Policy, Adapters, or AI scaffolds

## Quick start

```python
from evidence_repository import EvidenceRepositoryContainer

container = EvidenceRepositoryContainer.from_url(
    "postgresql+psycopg://user:pass@localhost:5432/xolaris",
    create_tables=True,
)

with container.session() as session:
    svc = container.build(session)
    result = svc.deduplication.ingest(finding, actor="ingest-pipeline")
    page = svc.search.open_findings(finding.tenant_id)
```

## Layout

```
evidence_repository/
  domain/           # FindingHistory, EvidenceVersion, LifecycleState
  interfaces/       # EvidenceRepository ABC
  persistence/      # ORM + PostgresEvidenceRepository + session factory
  services/         # Deduplication, Correlation, Search, Audit
  query/            # filters + pagination
  di/               # composition root
```

## Architecture doc

See ``docs/architecture/09-evidence-repository.md``.
"""
