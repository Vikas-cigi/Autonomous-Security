# Scan / Ingest Orchestrator
============================

Wires **Chat / API → Scanner adapters → Normalization → Evidence → Trust → Risk → Decision → Planner**.

**Position:** before the remediation control plane. Does not replace Approval /
Execution / Verification.

## Modes

| Mode | Behavior |
|------|----------|
| `simulate` (default) | Deterministic sample Nuclei/Trivy payloads — no binary required |
| `live` | `AdapterFactory` + real tool binary (Nuclei must be on PATH) |

## Quick start

```python
from uuid import uuid4
from models.common import ActorReference
from scan_ingest import ScanIngestContainer, ScanRequest, ScanMode

container = ScanIngestContainer.from_url("sqlite+pysqlite:///:memory:", create_tables=True)
request = ScanRequest(
    tenant_id=uuid4(),
    target="https://api.example.com",
    tool_name="nuclei",
    mode=ScanMode.SIMULATE,
    actor=ActorReference(actor_id=uuid4(), display_name="ops"),
    run_pipeline=False,
)
with container.session_scope(enable_pipeline=False) as svc:
    result = svc.engine.scan(request)
    print(result.status, result.findings_created)
```

## Chat TOOL path

`ScanAwareIntentRouter` classifies "scan https://…" as TOOL.
`ScanToolBuilder` runs this orchestrator and attaches `tool_results` for the LLM.

## HTTP

`POST /api/v1/scans` — see OpenAPI docs.
