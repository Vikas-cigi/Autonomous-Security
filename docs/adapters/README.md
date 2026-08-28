# Xolaris Adapter & Connector Plugin Guide

**Purpose:** One document for the team on how external security tools plug into Xolaris — today via **adapters**, tomorrow via **MCP tools** and **AI agents** — without rewriting the control plane.

**Audience:** Backend engineers adding scanners, connectors, or agent tools.

**Related docs:**
- Architecture overview: [08-security-tool-adapters.md](../architecture/08-security-tool-adapters.md)
- Adapter framework internals: [backend/src/adapters/ARCHITECTURE.md](../../backend/src/adapters/ARCHITECTURE.md)
- Scan entry point: [22-scan-ingest.md](../architecture/22-scan-ingest.md)

---

## 1. Vision — factory assembly line (Paul)

Xolaris is built like a **factory assembly line**, not one flat monolith:

```
┌─────────────┐   ┌──────────────┐   ┌─────────────┐   ┌──────────────┐
│ Scan/Ingest │ → │ Trust / Risk │ → │ Decision /  │ → │ Simulation / │
│  (adapters) │   │              │   │   Planner   │   │   Approval   │
└─────────────┘   └──────────────┘   └─────────────┘   └──────────────┘
                                                              ↓
                        ┌──────────────┐   ┌──────────────────────────┐
                        │ Verification │ ← │ Execution                │
                        └──────────────┘   └──────────────────────────┘
                                      ↓
                        ┌──────────────┐
                        │  Reporting   │
                        └──────────────┘
```

| Concept | Meaning |
|---------|---------|
| **Core MVP (hardwired)** | Trust, Risk, Decision, Planner, Simulation, Approval, Execution, Verification, Reporting |
| **Plug-in / plug-out** | Scanner adapters, future MCP connectors, optional tools |
| **Goal** | Add a new tool in **~1 hour to 1 day**, not rewrite the platform |

Each station does **one job**. Findings move down the line as canonical objects — never as vendor-specific JSON inside core engines.

---

## 2. What an adapter is (and is not)

### An adapter IS

- The **hexagonal port** between an external security tool and Xolaris
- Responsible for: auth → scope → **policy ALLOW** → run tool → parse stdout → **`RawResult`**
- Registered in `AdapterRegistry`, constructed via `AdapterFactory`

### An adapter is NOT

- A finding creator (`SecurityFindingObject` belongs to **Normalization**)
- A place for Trust/Risk/Decision logic
- A reason to modify Approval, Execution, or Reporting

### Contract (non-negotiable)

```
External tool  →  Adapter  →  RawResult
                                ↓
                    NormalizationService  →  SecurityFindingObject
                                ↓
                    EvidenceRepository (dedup/ingest)
                                ↓
                    Trust → Risk → Decision → Plan → …
```

---

## 3. Built-in adapters today

| Tool key | Adapter path | Normalizer | Typical use |
|----------|--------------|------------|-------------|
| `nuclei` | `src/adapters/nuclei/` | `normalization/adapters/nuclei_normalizer.py` | Web / network vuln scan |
| `trivy` | `src/adapters/trivy/` | `normalization/adapters/trivy_normalizer.py` | Container / image / FS vuln |
| `prowler` | `src/adapters/prowler/` | `normalization/adapters/prowler_normalizer.py` | AWS cloud security |
| `checkov` | `src/adapters/checkov/` | `normalization/adapters/checkov_normalizer.py` | IaC misconfiguration |
| `grype` | *(normalizer only today)* | `normalization/adapters/grype_normalizer.py` | Image vuln (adapter TBD) |

Registration happens in `src/adapters/bootstrap.py` (import side-effect).

---

## 4. How tools enter the platform (three front doors)

All three call the **same engines** underneath:

| Entry | Today | Calls |
|-------|-------|-------|
| **HTTP API** | `POST /api/v1/scans` | `ScanIngestService` → adapter → normalize → evidence → pipeline |
| **Chat / agent tool** | `ScanAwareIntentRouter` + `ScanToolBuilder` | Same orchestrator |
| **Direct Python** | `AdapterFactory.create(...).run(context)` | Adapter only; caller runs normalize + ingest |

```
Operator (API / Chat / Agent)
        ↓
   Scan / Ingest Orchestrator  (backend/scan_ingest/)
        ↓
   AdapterFactory → BaseToolAdapter.run() → RawResult
        ↓
   NormalizationService.normalize(tool, raw_output, ctx)
        ↓
   Evidence deduplication.ingest()
        ↓
   Optional: Trust → Risk → Decision → Planner
```

**Simulate mode:** When the real binary is not installed, `ScanMode.SIMULATE` uses sample payloads — same normalize/ingest/pipeline path.

---

## 5. Checklist — add a new scanner adapter

**Estimated effort:** 1–4 hours for a simple CLI tool; up to 1 day for API-based or auth-heavy tools.

### Step 1 — Create adapter package

```
backend/src/adapters/<tool_name>/
├── __init__.py
├── config.py      # extends AdapterConfig (binary_path, timeouts, tool-specific knobs)
├── parser.py      # vendor stdout/JSON → Python dict/list
└── adapter.py     # extends BaseToolAdapter
```

### Step 2 — Implement the adapter

```python
# adapter.py (minimal pattern)
from src.adapters.base.base_adapter import BaseToolAdapter, CommandResult
from src.adapters.base.raw_result import RawResultStatus
from src.adapters.base.registry import AdapterRegistry
from src.adapters.common.execution_context import AdapterExecutionContext

@AdapterRegistry.register("mytool")
class MyToolAdapter(BaseToolAdapter):
    tool_name = "mytool"

    def build_command(self, context: AdapterExecutionContext) -> list[str]:
        return [self._config.binary_path, *context.targets]

    def parse(self, stdout: str, stderr: str, exit_code: int):
        return MyToolParser().parse(stdout, stderr, exit_code)

    def map_status(self, result: CommandResult) -> RawResultStatus:
        return RawResultStatus.SUCCEEDED if result.exit_code == 0 else RawResultStatus.FAILED
```

**Lifecycle inherited from `BaseToolAdapter.run()`:**

```
initialize → authenticate → validate_scope → validate_policy →
prepare → execute → collect_metadata → parse → build_raw_result → cleanup
```

Policy: only `PolicyVerdict.ALLOW` runs the binary. Otherwise `POLICY_DENIED` — never execute without policy.

### Step 3 — Register in bootstrap

```python
# src/adapters/bootstrap.py
from src.adapters.mytool.adapter import MyToolAdapter  # noqa: F401
```

### Step 4 — Add normalizer (required for findings)

```
backend/normalization/adapters/mytool_normalizer.py
```

- Subclass `BaseNormalizer`
- Implement `tool_key`, `source_tool`, `extract_items`, `normalize_item`
- Register in `NormalizationService.default_normalizers()` **or** call `service.register(normalizer)` at startup

**Rule:** Adapter key and normalizer `tool_key` must match (e.g. both `"mytool"`).

### Step 5 — Wire Scan / Ingest (if scannable via orchestrator)

In `backend/scan_ingest/services/scan_orchestrator.py`:

1. Add config class to `_CONFIGS` dict for **live** mode
2. Add sample payload in `backend/scan_ingest/sample_payloads.py` for **simulate** mode

### Step 6 — Tests

| Test | Location |
|------|----------|
| Parser unit test | `tests/test_adapters.py` or `tests/adapters/test_mytool.py` |
| Adapter run (mock subprocess) | Same |
| Normalizer round-trip | `tests/test_normalization*.py` |
| End-to-end simulate scan | `tests/test_scan_ingest.py` |

### Step 7 — Document

- Add row to **Built-in adapters** table (this doc)
- Note binary install / env vars in adapter `config.py` docstring
- Update OpenAPI examples if HTTP-facing

---

## 6. Execution context (what callers must supply)

```python
from uuid import uuid4
from models.common import ActorReference
from models.enums import ActionClass, PolicyScope
from src.adapters.common.execution_context import AdapterExecutionContext

context = AdapterExecutionContext(
    tenant_id=uuid4(),
    asset_id=uuid4(),
    user=ActorReference(actor_id=uuid4(), display_name="secops"),
    roles=["secops"],
    scope=PolicyScope.TENANT,
    action_class=ActionClass.SIMULATE,  # or READ for passive tools
    targets=["https://example.com"],
    allowed_targets=["https://example.com"],
)
```

| Field | Required | Notes |
|-------|----------|-------|
| `tenant_id`, `asset_id`, `user` | Yes | Multi-tenant + audit |
| `targets` | Usually | Must ⊆ `allowed_targets` when set |
| `roles` | Recommended | Policy engine uses for ALLOW/DENY |
| `action_class` | Yes | `SIMULATE` for dry-run scans |

---

## 7. Quick usage examples

### Direct adapter (library)

```python
import src.adapters  # registers bootstrap
from src.adapters.base.factory import AdapterFactory
from src.adapters.nuclei.config import NucleiAdapterConfig

factory = AdapterFactory()
adapter = factory.create("nuclei", NucleiAdapterConfig())
raw = adapter.run(context)  # RawResult only
```

### Full ingest path (API)

```http
POST /api/v1/scans
Content-Type: application/json

{
  "tenant_id": "00000000-0000-4000-8000-000000000001",
  "target": "https://api.example.com",
  "tool_name": "nuclei",
  "mode": "simulate",
  "run_pipeline": true
}
```

### Chat

```
scan https://api.example.com with nuclei
```

Intent → TOOL → `ScanToolBuilder` → orchestrator → LLM summarizes results.

---

## 8. Future — MCP tools & AI agents

Same **plug-in** idea, different surface:

```
┌─────────────────────────────────────────────────────────┐
│  AI Agent (loop: plan → act → observe → next step)       │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   MCP: scan_target    MCP: get_finding    MCP: submit_approval
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                    Thin tool wrappers
                            │
              Adapters / Engine facades (same as APIs)
                            │
                    Xolaris control plane
```

| Layer | Role |
|-------|------|
| **Adapter** | Runs external scanner → `RawResult` |
| **MCP tool** | Standard agent-callable capability (scan, approve, verify…) |
| **AI agent** | Chooses next tool; must respect policy gates |

### Rules for agent + MCP (same as adapters)

1. Agent **calls** engines — never bypasses Approval or Execution authorization
2. Tools return **structured results** (like `ToolResult` / `ScanResult.to_chat_summary()`)
3. New capability = new **tool wrapper** + existing engine — not a new monolith path
4. Document each MCP tool like an adapter: inputs, outputs, policy requirements, example

### Suggested MCP tool roadmap

| Phase | Tools |
|-------|-------|
| **Now** | `scan_target` (via Scan/Ingest) |
| **Next** | `get_finding`, `score_trust`, `score_risk`, `decide`, `create_plan` |
| **Later** | `simulate_plan`, `submit_approval`, `execute_plan`, `verify_remediation` |

Each tool maps 1:1 to an existing engine facade or adapter — **plug in, plug out**.

---

## 9. What you do NOT change when adding a tool

| Module | Change? |
|--------|---------|
| Trust / Risk / Decision / Planner | No |
| Simulation / Approval / Execution / Verification | No |
| Reporting & Analytics | No |
| Evidence / Asset domain models | No |
| Policy Engine core | No (adapter *calls* it) |

**Only touch:** adapter package, normalizer, scan_ingest config/samples, tests, this doc.

---

## 10. Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `AdapterNotFoundError` | Missing `@AdapterRegistry.register` or bootstrap import |
| `POLICY_DENIED` | PolicyEngine DENY/ESCALATE — check `roles`, `action_class`, default rules |
| `No normalizer registered` | Normalizer not added or `tool_key` mismatch |
| Scan succeeds, 0 findings | Parser returned empty; check `raw.raw_output` vs stdout |
| Live mode fails | Binary not on PATH — use `simulate` until installed |

---

## 11. Summary

> **Adapters plug scanners into the factory line. Normalizers standardize output. Scan/Ingest feeds the assembly line. MCP and AI agents are the next front door — same engines, same rules.**

When in doubt: return **`RawResult` only**, normalize separately, never rewrite core engines.
