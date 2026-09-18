# Xolaris handoff

**Audience:** next engineer taking Feature **4.7 One-Month Go-Live** (22 working days).  
**Source plan:** [docs/planning/Xolaris-LOE-1-Month.html](docs/planning/Xolaris-LOE-1-Month.html) (also `.docx` / `.pdf` in the same folder).  
**Repo:** `https://github.com/Vikas-cigi/Autonomous-Security` · branch `dev`.  
**Do not rebuild engines.** Host them, persist data, prove a live demo.

**Read first:** [§2 Theory](#2-theory-how-xolaris-works-in-depth) — why the line exists, trust vs risk, why RavenX is not the system of record.  
**Local RavenX on this laptop:** [§7](#7-ravenx-model-download--hugging-face) then [§8](#8-llamacpp--install-and-run-including-windows).  
**Download the GGUF from the command line:** [PowerShell §7.4](#74-windows-powershell-cli) · [CMD §7.5](#75-windows-command-prompt-cmd) · [Linux GPU VM §7.6](#76-linux-gpu-vm-vastai--aws--any-ssh-box).

---

## 1. What this platform is

Xolaris is an **autonomous cybersecurity remediation control plane**, not a chatbot.

It ingests scanner output, stores canonical findings, scores trust and risk, decides, plans, simulates, waits for approval, then can execute and verify. Chat is one front door. HTTP is another. Both must call the **same engines**.

**Go-live definition (end of week 4):**

1. `/chat` answers from **RavenX** via **llama.cpp** on a GPU VM.  
2. A **live** Nuclei or Trivy scan (not simulate-only) writes findings.  
3. `GET /api/v1/findings` and `GET /api/v1/assets` still work **after a process restart** (PostgreSQL).  
4. APIs require an **API key** (not an open internet).  
5. After a plan is created, **simulation runs** and an **approval is submitted**. Execution stays the current recording adapter (no real patch).

Read **§2 Theory** before installing tools. Commands without that model lead to wiring scanners into the wrong layer.

---

## 2. Theory: how Xolaris works (in depth)

This section is the product model. Diagrams and runtime are in §3. Commands are in §6 onward. Architecture contracts live in [docs/architecture/](docs/architecture/README.md).

### 2.1 The problem it is built to solve

Security teams already have scanners (Nuclei, Trivy, Prowler, cloud CSPM, IaC checkers). Those tools dump **vendor JSON**: different field names, different severity scales, duplicates across tools, no company-wide “what do we do next?”, and no safe path from “we saw a CVE” to “we changed production.”

If you feed raw Nuclei JSON into an LLM and let it SSH to a server, you get:

- Hallucinated CVEs and unofficial “just run this command” fixes  
- No proof the finding was real (no evidence hash, no tenant boundary)  
- No distinction between “we are confident this is true” and “this would hurt the business”  
- Accidental patches on the wrong customer’s asset  

Xolaris is a **control plane**: scanners remain plug-ins; **truth, risk, permission, and change** are owned by Xolaris objects and engines. The LLM (RavenX) **explains and assists**. It does not become the system of record.

### 2.2 Assembly line (one station, one job)

Think of a factory, not a monolith. A finding is a unit of work that moves down a line. Each station **must not** do the next station’s job.

| Station | Question it answers | Must not do |
|---------|---------------------|-------------|
| Adapter | Did this tool run, and what did it print? | Invent a finding schema |
| Normalization | What is this in **our** language? | Score risk or call the LLM |
| Evidence | Have we stored proof, and is it a duplicate? | Decide to patch |
| Assets | What machine/app does this belong to? | Run scanners |
| Trust | How much should we **believe** this finding? | Say how urgent the business impact is |
| Risk | If it is real, how bad is it **for this company**? | Write a runbook |
| Decision | **Remediate, mitigate, escalate, monitor, or ignore?** | Execute SSH/cloud APIs |
| Planner | What **steps and rollback** would that take? | Touch infrastructure |
| Simulation | If we did those steps, what would break? | Apply the change |
| Approval | Has a human/org **authorized** execution? | Run the change |
| Execution | Carry out approved steps (or record them) | Re-score risk or rewrite the plan |
| Verification | Did the finding actually go away? | Invent a new plan |
| Reporting | What should leadership see? | Mutate upstream engines |

If you put Nuclei JSON inside the planner, or let chat skip Approval, the line is broken. New tools **plug in at the adapter station only**.

### 2.3 Canonical objects vs raw scanner JSON

**Canonical** means one internal shape the rest of the platform understands: `SecurityFindingObject`, `EvidenceObject`, `DecisionObject`, plan/simulation/approval/verification types in `backend/models/`.

Nuclei might say `info.severity` + `matched-at`. Trivy might say `VulnerabilityID` + `PkgName`. Those strings **die at normalization**. After that, every engine sees:

- `tenant_id`, `asset_id`, `finding_id`  
- `severity` (`critical` … `informational`)  
- `cve_ids`, `title`, `description`, `evidence[]`  
- `status` (new, remediating, resolved, …)  

**Theory:** AI prompts, reports, and remediation must consume canonical fields. If you prompt RavenX with raw scanner blobs, you re-introduce vendor drift and you cannot audit “which official finding id did we act on?”

Evidence is **content-addressed proof** (hash + lineage + which tool). A finding without evidence is an allegation. Dedup uses a **fingerprint** so two Nuclei runs on the same CVE/host merge instead of creating two tickets.

### 2.4 Hexagonal adapters (why scanners are not the core)

The core never imports “Nuclei types.” It depends on a **port**: `BaseToolAdapter.run(context) → RawResult`.

Lifecycle (template method): authenticate → validate scope → **policy ALLOW** → execute binary → parse stdout → `RawResult`.

- **Hexagon:** business logic in the middle; tools on the outside. Swap Nuclei for another web scanner without touching Trust/Risk/Planner.  
- **Policy before binary:** if the rule says DENY, the scanner process is not started (`POLICY_DENIED`).  
- **Simulate vs live:** same stations after ingest. Simulate injects **sample payloads** so the line can be tested without Nuclei installed. Live runs the real CLI. Normalization and evidence do not care which door you used.

### 2.5 Policy: fail closed

`ActionClass`: READ, SUGGEST, PLAN, SIMULATE, EXECUTE_LOW, EXECUTE_HIGH.

**Fail closed:** no matching rule ⇒ **DENY**. Execute-high must never silently ALLOW. Verdicts: ALLOW, DENY, ESCALATE.

This is **authorization of an action**, not “is the CVE real?” A high-trust finding can still be DENY for EXECUTE_HIGH if the actor is not secops/admin. Local rules exist today; OPA is a stub (out of the 22-day plan).

### 2.6 Multi-tenancy

Every durable record carries `tenant_id`. Search APIs **require** it. Engine A’s Postgres row is invisible to tenant B even on the same database.

**Theory:** Xolaris is built as a control plane for **many companies** (or many orgs in one company). SQLite vs Postgres is a **durability** choice; tenant_id is an **isolation** choice. Week 3 checks isolation; it does not invent tenancy — the models already have it.

Chat memory today is **not** tenant-durable (RAM). That is a hole: session_id is not a tenant. Week 3 must store messages with tenant + session.

### 2.7 Trust vs risk (two different scores)

People collapse “confidence” and “severity.” Xolaris splits them on purpose.

**Trust (0–100)** — *Is this finding true enough to act?*  
False positives, weak evidence, unvalidated scanner noise → low trust → recommend investigate/defer even if the title says “critical.” High trust + validated evidence → “act.”

**Risk (0–100)** — *If it is true, how bad is it for this enterprise?*  
Uses trust as an **input**, plus severity/CVSS hints, asset criticality, exposure, compliance/business/technical/operational impact. Output includes **priority (P1–P5)** and **SLA** (immediate, 24h, 7d, …).

A noisy Nuclei template on a lab VM: low trust, maybe medium risk.  
A validated RCE on a public payments host: high trust, P1 risk.

Decision Service consumes **both**. Planner consumes the decision, not raw CVSS alone.

```text
Scanner severity  ≠  Trust  ≠  Enterprise risk  ≠  Decision  ≠  Permission to execute
```

### 2.8 Decision Service vs Decision Engine (two different “decisions”)

| Name | Package | Meaning |
|------|---------|---------|
| **Decision Engine** | `decision_engine/` | Chat **intent**: CHAT vs TOOL (scan) vs RAG vs AGENT |
| **Decision Service** | `decision_service/` | **What to do about a finding**: remediate / mitigate / escalate / monitor / ignore |

Mixing them is the most common onboarding mistake. `/chat` uses Decision Engine. The scan pipeline uses Decision Service (`decide()`), usually **deterministic** (`DECISION_ENABLE_AI_STACK=false`). Optional AI on decisions is a flag, not the default, because remediation choices must be **replayable and auditable**.

### 2.9 From decision to change (plan → sim → approve → exec → verify)

**Planner** turns “REMEDIATE” into ordered **steps**, dependencies, rollback, time/cost estimates. It does **not** SSH. It does **not** call RavenX.

**Simulation** is a **dry-run of the plan**, not a second scan. It estimates blast radius, downtime, rollback feasibility, policy conflict. `safe_to_execute` is an input to humans, not a license to skip approval.

**Approval** is the **organizational gate**. Output is `ExecutionAuthorization` (token: this plan, this tenant, not expired). Execution Engine **refuses** unauthorized work.

**Execution** runs steps via an **infrastructure adapter**. Today that adapter **records success** without changing servers (safe for demos). Real cloud/SSH adapters are backlog: same orchestrator, different adapter.

**Verification** asks: after execution, is the finding gone? New evidence, comparison, status. It is not “the LLM said it’s fine.”

**Reporting** is **read-only** snapshots for dashboards and compliance. It must not write back into Trust or mutate findings as a side effect.

**Why we do not auto-execute:** a control plane that patches production without simulation + approval is an exploit chain. Week 4 auto-runs **simulation** and **submits** approval (pending). A human still approves. Execution stays recording-only this month.

### 2.10 Deterministic core vs RavenX (AI)

| Layer | Default | Why |
|-------|---------|-----|
| Trust, risk, plan, sim, approval routing | **Deterministic** | Same inputs → same outputs; auditors can replay |
| Chat `/chat` | **RavenX** via llama.cpp | Explanation, Q&A, optional “scan this URL” tool |
| Decision Service AI | **Off** | Finding actions should not depend on temperature |

RavenX is a **Qwen3-8B** security fine-tune using a **RATH** loop (Risk/Identify → Assess → Threat → Highlight/Remediate → Document → Prevent). That is a **narrative protocol** for the model’s answers. It is **not** a replacement for `TrustAssessment` or `RiskAssessment` rows in the database.

If llama.cpp is down, **scans and engines still work**. If RavenX hallucinates a CVE, the **canonical finding** from Nuclei/Trivy is still the record. Never write the model’s story back as a `SecurityFindingObject` without going through adapters + normalization.

### 2.11 Chat as a front door, not the product

Operator paths:

1. **HTTP** `POST /api/v1/scans` — machines, CI, Swagger.  
2. **Chat** — human language; intent router may call the **same** scan orchestrator.  
3. **Python** `AdapterFactory.create(...).run()` — tests and future agents.

All three must converge on Evidence → pipeline. An agent that bypasses Approval is out of policy (see adapters guide). MCP tools later wrap **existing** facades; they do not create a second pipeline.

### 2.12 Worked example (one finding)

1. Operator (or chat) asks to scan `https://lab.example` with Nuclei, `mode=live`.  
2. Policy allows SIMULATE/scan action for that tenant/role.  
3. Nuclei returns JSONL matches. Adapter wraps stdout in `RawResult`.  
4. Normalizer emits `SecurityFindingObject` (e.g. outdated SSH, CVE list, severity high).  
5. Asset inventory upserts host `lab.example`. Evidence stores hashed proof; fingerprint may **merge** a duplicate.  
6. Trust: evidence validated, scanner known → relatively high trust.  
7. Risk: internet-facing + high severity → high enterprise risk, tight SLA.  
8. Decision: REMEDIATE (deterministic advisor).  
9. Planner: steps (upgrade OpenSSH, validate config, rollback to previous package).  
10. *(Week 4)* Simulation: service restart window; `safe_to_execute` true/false + warnings.  
11. *(Week 4)* Approval request **pending** for secops.  
12. After human approve: Execution records steps (demo) or later applies them.  
13. Verification: rescan or evidence that version changed.  
14. Reporting: counts this in open-critical / MTTR metrics.

Steps 10–14 exist as engines; auto-chain through 11 is the remaining glue.

### 2.13 What “autonomous” means here

Not “the model roots the box.” It means:

- Ingest and scoring run **without a human per finding**  
- Plans are generated **deterministically** from decisions  
- Humans stay on the **authorization** loop for destructive work  
- AI is used where language helps (chat, optional decision assist), not where math and policy must be stable  

That is why the 22-day plan hosts RavenX **and** Postgres **and** live Nuclei, but still **does not** turn on real execution adapters.

---

## 3. Architecture

Canonical module docs: [docs/architecture/README.md](docs/architecture/README.md).

### 3.1 Control-plane pipeline

```
Scan/Ingest → Evidence → Trust → Risk → Decision → Plan
          → Simulation → Approval → Execution → Verification → Reporting
```

Today `FindingPipelineService` (`backend/scan_ingest/services/finding_pipeline.py`) stops at **Plan**. Simulation and Approval exist as APIs but are **not auto-chained**. That chain is a week-4 task.

### 3.2 Platform map

```mermaid
flowchart TB
    subgraph Ingest
        Tools[Scanners: Nuclei Trivy Prowler Checkov Grype]
        Adapters[Tool Adapter Framework]
        Raw[RawResult]
        Norm[Normalization Service]
        Findings[SecurityFindingObject]
    end

    subgraph Governance
        Policy[Policy Engine]
        Canon[Canonical Security Objects]
    end

    subgraph Catalog
        Assets[Asset Inventory]
        Evidence[Evidence Repository]
        ThreatIntel[Threat Intelligence]
        Trust[Trust Scoring]
        Risk[Risk Engine]
    end

    subgraph AI
        Chat["/chat LLMService"]
        Llama[llama.cpp :8080]
        RavenX[RavenX-Sec-8B GGUF]
        DE[Decision Engine]
        CM[Context Manager]
        PB[Prompt Builder]
        PF[Provider Factory]
    end

    Tools --> Adapters --> Raw --> Norm --> Findings
    Findings --> Canon
    Findings --> Evidence
    Findings -->|asset_id| Assets
    Findings --> Trust
    Evidence --> Trust
    Assets --> Trust
    ThreatIntel --> Trust
    Trust --> Risk
    Risk --> DecisionSvc[Decision Service]
    DecisionSvc --> Planner[Remediation Planner]
    Planner --> Sim[Simulation]
    Sim --> Approval
    Approval --> Exec[Execution]
    Exec --> Verify[Verification]
    Verify --> Reporting
    Chat --> DE --> CM --> PB --> PF --> Llama --> RavenX
    Chat -->|scan intent| Adapters
```

### 3.3 Runtime (what you actually start)

```mermaid
flowchart LR
    Browser[Browser / curl]
    API[FastAPI uvicorn :8000]
    LLM[llama.cpp server :8080]
    GGUF[RavenX GGUF on disk]
    PG[(PostgreSQL :5432)]
    SQLite[(SQLite xolaris.db default local)]
    Binaries[nuclei / trivy on PATH]

    Browser --> API
    API -->|POST /v1/chat/completions| LLM
    LLM --> GGUF
    API --> PG
    API --> SQLite
    API -->|mode=live| Binaries
```

| Process | Port | Role |
|---------|------|------|
| `uvicorn app:app` from `backend/` | 8000 | Control plane + `/chat` + `/api/v1/*` |
| `llama-server` | 8080 | OpenAI-compatible chat; `LLAMA_BASE_URL` |
| Postgres 16 | 5432 | Hosted / durable store (`DATABASE_URL`) |
| Vite frontend | 5173 | Prototype UI (still mock until week 4) |

**Chat path (already coded):**  
`POST /chat` → `LLMService` → DecisionEngine (`ScanAwareIntentRouter`) → ContextManager → PromptBuilder → `LlamaProvider` → `http://127.0.0.1:8080/v1/chat/completions`.

**Scan path (already coded):**  
`POST /api/v1/scans` → resolve/create asset → adapter (`simulate` sample JSON **or** live binary) → normalize → evidence ingest → optional Trust → Risk → Decision → Plan.

### 3.4 Module status (do not rebuild Done)

| # | Module | Status | Notes for the next person |
|---|--------|--------|---------------------------|
| 5–6, 9–10, 12–18, 20–21 | Domain engines + reporting | Done | Use APIs; do not rewrite |
| 4.6 | Findings/Assets HTTP | Done | `GET /api/v1/findings`, `GET /api/v1/assets` |
| 1–4 | AI V2 | Partial | Wired to chat; RAG empty; OpenAI/Anthropic placeholders |
| 7 | Policy | Partial | Local rules work; OPA not this month |
| 8, 22 | Adapters + scan | Partial | Code yes; **binaries** only on Linux host |
| 11 | Threat intel | Partial | Feeds skipped; not this month |
| 19 | Execution | Partial | Records success; **no real infra** this month |
| UI | React | Partial | Mock data; wire **one** findings list in week 4 |

Architecture index still says some V2 modules are “not wired”; **chat V2 is wired** (`LLM_ENABLE_V2_STACK=True`). Trust the code in `backend/services/llm_service.py`.

---

## 4. Repository map

| Path | What |
|------|------|
| `backend/app.py` | FastAPI app, CORS, routers |
| `backend/core/config.py` | `.env` settings |
| `backend/api/v1/` | HTTP: chat, scans, findings, assets, engines |
| `backend/api/deps.py` | DI containers (shared evidence/assets with scan) |
| `backend/src/adapters/` | Nuclei, Trivy, Prowler, Checkov, Grype |
| `backend/normalization/` | Raw JSON → `SecurityFindingObject` |
| `backend/scan_ingest/` | Orchestrator + pipeline to Plan |
| `backend/docker-compose.yml` | Postgres 16 |
| `backend/tests/` | Unit tests (run from `backend/`) |
| `frontend/` | Vite + React mock UI |
| `docs/architecture/` | Module contracts |
| `docs/adapters/README.md` | How to add a scanner |
| `docs/planning/` | LOE HTML/Word/PDF |

**Git:** work on `dev`. Author identity on this machine: `Vikas-cigi`. Do not commit `.env` or GGUF weights.

---

## 5. How a request works (detail)

See **§2 Theory** for *why* these requests exist. This section is the HTTP/chat mechanics.

### 5.1 Chat

1. Client `POST /chat` with `{ "message": "...", "session_id": "optional" }`.  
2. If the message looks like a scan (`scan https://…`), intent is `TOOL` and `ScanToolBuilder` runs the same scan orchestrator.  
3. Otherwise the LLM answers using RavenX (once llama.cpp is up).  
4. **Today** history is **in RAM** (`MemoryService`, last 20 messages). Restart wipes chat. Week 3 replaces this with Postgres.

### 5.2 Scan

Body of `POST /api/v1/scans`:

```json
{
  "tenant_id": "00000000-0000-4000-8000-000000000001",
  "target": "https://example.com",
  "tool_name": "nuclei",
  "mode": "simulate",
  "run_pipeline": true,
  "invoke_ai_decision": false
}
```

| `mode` | Behaviour |
|--------|-----------|
| `simulate` | Sample payload; **no** Nuclei binary. Use this on Windows laptops. |
| `live` | Runs `nuclei` / `trivy` / … from `PATH`. Needs Linux + installed tools. |

`run_pipeline: true` scores trust/risk, decides, and may create a plan. It does **not** simulate or submit approval until you implement W4.2.

### 5.3 Findings after scan

Use the **same** `tenant_id`:

```http
GET /api/v1/findings?tenant_id=00000000-0000-4000-8000-000000000001
GET /api/v1/findings/{finding_id}?tenant_id=...
GET /api/v1/findings/{finding_id}/history?tenant_id=...
GET /api/v1/assets?tenant_id=...
```

Wrong tenant → not-found envelope (`success: false`), not another tenant’s rows.

---

## 6. Local testing (Windows laptop)

You can prove the **control plane without GPU** using simulate mode + SQLite.

### 6.1 Prerequisites

- Python 3.11 or 3.12 on PATH (not the Microsoft Store stub).  
- Git.  
- Optional: Docker Desktop if you want Postgres locally.  
- Optional: Node 20+ for the frontend.  
- llama.cpp + GGUF are **required for `/chat`**. Follow §7 then §8. Scans still work without them.

### 6.2 Backend

```powershell
cd C:\Users\CIGI-USER\Downloads\Autonomous-Security\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Open `http://localhost:8000/docs`.

Health: `GET http://localhost:8000/health` → `{ "status": "healthy" }`.

### 6.3 Simulate scan (no scanner binaries)

```powershell
$tenant = "00000000-0000-4000-8000-000000000001"
$body = @{
  tenant_id = $tenant
  target = "https://demo.xolaris.local"
  tool_name = "nuclei"
  mode = "simulate"
  run_pipeline = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/scans" -ContentType "application/json" -Body $body
Invoke-RestMethod "http://localhost:8000/api/v1/findings?tenant_id=$tenant"
Invoke-RestMethod "http://localhost:8000/api/v1/assets?tenant_id=$tenant"
```

### 6.4 Unit tests

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
python -m unittest tests.test_findings_assets_api tests.test_scan_ingest -v
```

### 6.5 Optional local Postgres

```powershell
cd backend
docker compose up -d
```

Create `backend/.env` (never commit):

```
DATABASE_URL=postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris
CREATE_TABLES=true
```

Restart uvicorn. Re-run the simulate scan; data survives uvicorn restart.

### 6.6 Local chat (RavenX)

You need **two processes**: llama.cpp on `:8080` (the model) and FastAPI on `:8000` (Xolaris).

| Step | Section |
|------|---------|
| 1. Download the GGUF from Hugging Face | Windows **PowerShell §7.4** or **CMD §7.5**; Linux VM **§7.6** |
| 2. Install llama.cpp and start `llama-server` | **§8.1** (Windows) or §8.4 (Linux) |
| 3. Point FastAPI at it and call `/chat` | **§8.3** |

Until `:8080` is up, `POST /chat` fails. Scan APIs still work.

### 6.7 Frontend (mock only)

```powershell
cd frontend
npm install
npm run dev
```

`http://localhost:5173` — dummy data. CORS already allows 5173. Week 4: replace findings page `fetch` only.

---

## 7. RavenX model download (Hugging Face)

Xolaris does **not** download the model for you. FastAPI only **HTTP-calls** a local llama.cpp server. You put a **GGUF file on disk**, start llama.cpp pointing at that file, then set `LLAMA_BASE_URL`.

```text
Hugging Face  →  ravenx-....gguf on disk  →  llama-server :8080  →  FastAPI POST /chat
```

**Repo (public, Apache-2.0):** [https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF](https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF)

| Fact | Value |
|------|--------|
| Architecture | Qwen3-8B |
| Format | **GGUF** (llama.cpp). Not PyTorch `.safetensors`. |
| Context | Up to 128K tokens in the file; we run **4K–8K** locally |
| What it is for | Chat explanation (RATH narrative). Not the findings database. |
| Git | **Never commit** the GGUF (`*.gguf` is gitignored) |

### 7.1 Which file to download

Pick **one** file from the Hugging Face **Files** tab. Default for this project:

**`ravenx-sec-v4.0-128k-Q4_K_M.gguf`** (~4.7 GB)

| File | Quant | Disk | GPU VRAM | When |
|------|-------|------|----------|------|
| **`ravenx-sec-v4.0-128k-Q4_K_M.gguf`** | Q4_K_M | **~4.7 GB** | ~6–8 GB | **Use this** |
| `ravenx-sec-v4.0-128k-Q5_K_M.gguf` | Q5_K_M | ~5.4 GB | ~8–10 GB | Better quality, more RAM |
| `ravenx-sec-v4.0-128k-Q8_0.gguf` | Q8_0 | ~8.1 GB | ~10–12 GB | Strong GPU only |
| `ravenx-sec-v4.0-128k-f16.gguf` | F16 | ~15.3 GB | ~16 GB+ | Skip on laptops |

**CPU-only laptop:** still download **Q4_K_M**. It will be **slow** (tens of seconds to minutes per reply) but proves `/chat`. Do not download F16 onto a laptop.

Ollama is **not** what FastAPI expects. Skip Ollama unless you know how to point `LLAMA_BASE_URL` at Ollama’s OpenAI port.

### 7.2 Hugging Face account (usually optional)

The repo is **public**. You can download without a token.

If the CLI says `401` / `gated` / `Please login`:

1. Create a free account at [huggingface.co](https://huggingface.co).  
2. [Settings → Access Tokens](https://huggingface.co/settings/tokens) → **Read** token.  
3. PowerShell (current user, this session):

```powershell
$env:HF_TOKEN = "hf_xxxxxxxx"
```

Or store it once:

```powershell
python -m pip install -U "huggingface_hub[cli]"
hf auth login
```

Paste the token when asked. Do **not** commit the token or put it in the repo.

### 7.3 Pick the shell first

The model is **one GGUF file**. You download it with a CLI. Pick the row that matches where you are sitting, then copy the block in that section.

| Where you are | What to open | Section |
|---------------|--------------|---------|
| This Windows laptop | **PowerShell** (Win+X → Windows PowerShell / Terminal) | **§7.4** |
| This Windows laptop | **Command Prompt** (`cmd.exe`) | **§7.5** |
| Vast.ai, AWS EC2, or any Linux GPU VM | SSH, then **bash** | **§7.6** |
| WSL2 on this laptop | Ubuntu terminal | Same commands as **§7.6**, save under `/mnt/c/models/...` if you will run llama.cpp on Windows |

Put the file **outside** the git repo so you cannot `git add` 4.7 GB.

| OS | Save the GGUF here |
|----|--------------------|
| Windows laptop | `C:\models\RavenX-Sec-8B-GGUF\ravenx-sec-v4.0-128k-Q4_K_M.gguf` |
| Linux VM | `/opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf` |

Direct URL (same file, all methods):

`https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF/resolve/main/ravenx-sec-v4.0-128k-Q4_K_M.gguf`

After download, jump to **§7.7** to confirm size, then **§8** to run llama.cpp.

### 7.4 Windows PowerShell (CLI)

Open **PowerShell**. If `Activate.ps1` is blocked, run this once in the same window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Create the folder:

```powershell
New-Item -ItemType Directory -Force -Path C:\models\RavenX-Sec-8B-GGUF | Out-Null
```

#### Method A — Hugging Face CLI (preferred, resumable)

Needs a real Python on PATH (not the Microsoft Store stub). Use the backend venv if you already created it in §6.2.

```powershell
cd C:\Users\CIGI-USER\Downloads\Autonomous-Security\backend
.\venv\Scripts\Activate.ps1
python -m pip install -U "huggingface_hub[cli]"
hf download deadbydawn101/RavenX-Sec-8B-GGUF ravenx-sec-v4.0-128k-Q4_K_M.gguf --local-dir C:\models\RavenX-Sec-8B-GGUF
```

If `hf` is not found, use the older CLI name (same arguments):

```powershell
huggingface-cli download deadbydawn101/RavenX-Sec-8B-GGUF ravenx-sec-v4.0-128k-Q4_K_M.gguf --local-dir C:\models\RavenX-Sec-8B-GGUF
```

If neither command is on PATH, call Python directly (no `hf` binary needed):

```powershell
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='deadbydawn101/RavenX-Sec-8B-GGUF', filename='ravenx-sec-v4.0-128k-Q4_K_M.gguf', local_dir=r'C:\models\RavenX-Sec-8B-GGUF')"
```

No venv yet? Use system Python:

```powershell
py -m pip install -U "huggingface_hub[cli]"
py -m huggingface_hub.cli.hf download deadbydawn101/RavenX-Sec-8B-GGUF ravenx-sec-v4.0-128k-Q4_K_M.gguf --local-dir C:\models\RavenX-Sec-8B-GGUF
```

The download **resumes** if it dies. Re-run the same command.

If you get `401` / `gated`, set a token for this session then retry:

```powershell
$env:HF_TOKEN = "hf_xxxxxxxx"
```

#### Method B — `curl.exe` (no Python)

Use **`curl.exe`**, not `Invoke-WebRequest` (IWR is slow and can eat RAM on a 4.7 GB file).

```powershell
curl.exe -L --retry 5 -C - -o C:\models\RavenX-Sec-8B-GGUF\ravenx-sec-v4.0-128k-Q4_K_M.gguf "https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF/resolve/main/ravenx-sec-v4.0-128k-Q4_K_M.gguf"
```

`-C -` resumes a partial file. Re-run if the network drops.

#### Method C — Browser (not CLI)

1. Open [the model page](https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF).  
2. **Files and versions** → `ravenx-sec-v4.0-128k-Q4_K_M.gguf` → download.  
3. Move it to `C:\models\RavenX-Sec-8B-GGUF\`.

Then **§7.7**.

### 7.5 Windows Command Prompt (cmd)

Open **cmd**: Win+R → type `cmd` → Enter. Do **not** paste PowerShell backticks (`` ` ``) here; they are not line-continuation in cmd.

Create the folder:

```bat
if not exist C:\models\RavenX-Sec-8B-GGUF mkdir C:\models\RavenX-Sec-8B-GGUF
```

#### Method A — Hugging Face CLI (preferred)

```bat
cd /d C:\Users\CIGI-USER\Downloads\Autonomous-Security\backend
venv\Scripts\activate.bat
python -m pip install -U "huggingface_hub[cli]"
hf download deadbydawn101/RavenX-Sec-8B-GGUF ravenx-sec-v4.0-128k-Q4_K_M.gguf --local-dir C:\models\RavenX-Sec-8B-GGUF
```

If `hf` is not recognized:

```bat
huggingface-cli download deadbydawn101/RavenX-Sec-8B-GGUF ravenx-sec-v4.0-128k-Q4_K_M.gguf --local-dir C:\models\RavenX-Sec-8B-GGUF
```

If the CLI still is not on PATH:

```bat
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='deadbydawn101/RavenX-Sec-8B-GGUF', filename='ravenx-sec-v4.0-128k-Q4_K_M.gguf', local_dir=r'C:\models\RavenX-Sec-8B-GGUF')"
```

No venv:

```bat
py -m pip install -U "huggingface_hub[cli]"
py -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='deadbydawn101/RavenX-Sec-8B-GGUF', filename='ravenx-sec-v4.0-128k-Q4_K_M.gguf', local_dir=r'C:\models\RavenX-Sec-8B-GGUF')"
```

Token for this cmd window (only if Hugging Face returns 401):

```bat
set HF_TOKEN=hf_xxxxxxxx
```

#### Method B — `curl.exe` (no Python)

```bat
curl.exe -L --retry 5 -C - -o C:\models\RavenX-Sec-8B-GGUF\ravenx-sec-v4.0-128k-Q4_K_M.gguf "https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF/resolve/main/ravenx-sec-v4.0-128k-Q4_K_M.gguf"
```

#### Verify in cmd

```bat
dir C:\models\RavenX-Sec-8B-GGUF\ravenx-sec-v4.0-128k-Q4_K_M.gguf
```

The size column should be about **4.7 GB** (around 5,000,000,000 bytes). A 1 KB file is an HTML error page — delete it and retry.

Then **§7.7** / **§8.1**.

### 7.6 Linux GPU VM (Vast.ai / AWS / any SSH box)

Do this **on the VM**, not on the laptop. Rent the box first (§11.1), then SSH:

```bash
ssh -p <PORT> root@<HOST>
```

On AWS, that may be `ubuntu@<HOST>` with `-i your-key.pem`.

#### 0) Disk, GPU, packages

You need **≥ 8 GB free** (4.7 GB file + headroom). Hugging Face is slow on a cold VM — start this on day 1.

```bash
nvidia-smi
df -h
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git wget curl tmux
sudo mkdir -p /opt/models/RavenX-Sec-8B-GGUF
```

Start a **tmux** session so the download survives if SSH drops:

```bash
tmux new -s ravenx
```

If you disconnect: `tmux attach -t ravenx`. Detach without killing it: `Ctrl+B` then `D`.

Optional token (only if the CLI returns 401):

```bash
export HF_TOKEN=hf_xxxxxxxx
```

#### Method A — Hugging Face CLI (preferred, resumable)

```bash
python3 -m pip install -U "huggingface_hub[cli]"
hf download deadbydawn101/RavenX-Sec-8B-GGUF ravenx-sec-v4.0-128k-Q4_K_M.gguf --local-dir /opt/models/RavenX-Sec-8B-GGUF
```

If `hf` is not found:

```bash
huggingface-cli download deadbydawn101/RavenX-Sec-8B-GGUF ravenx-sec-v4.0-128k-Q4_K_M.gguf --local-dir /opt/models/RavenX-Sec-8B-GGUF
```

If neither binary is on PATH:

```bash
python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='deadbydawn101/RavenX-Sec-8B-GGUF', filename='ravenx-sec-v4.0-128k-Q4_K_M.gguf', local_dir='/opt/models/RavenX-Sec-8B-GGUF')"
```

Re-run the same command to **resume**.

Faster CLI (optional, after `pip install -U hf_transfer`):

```bash
export HF_HUB_ENABLE_HF_TRANSFER=1
hf download deadbydawn101/RavenX-Sec-8B-GGUF ravenx-sec-v4.0-128k-Q4_K_M.gguf --local-dir /opt/models/RavenX-Sec-8B-GGUF
```

#### Method B — `wget` (resume with `-c`)

```bash
wget -c "https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF/resolve/main/ravenx-sec-v4.0-128k-Q4_K_M.gguf" -O /opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf
```

Leave SSH: wrap it so it keeps going after disconnect:

```bash
nohup wget -c "https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF/resolve/main/ravenx-sec-v4.0-128k-Q4_K_M.gguf" -O /opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf > /tmp/ravenx-download.log 2>&1 &
tail -f /tmp/ravenx-download.log
```

#### Method C — `curl` (resume with `-C -`)

```bash
curl -L --retry 5 -C - -o /opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf "https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF/resolve/main/ravenx-sec-v4.0-128k-Q4_K_M.gguf"
```

#### Method D — `aria2c` (multi-connection, often fastest on GPU VMs)

```bash
sudo apt-get install -y aria2
aria2c -c -x 16 -s 16 -k 1M -d /opt/models/RavenX-Sec-8B-GGUF -o ravenx-sec-v4.0-128k-Q4_K_M.gguf "https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF/resolve/main/ravenx-sec-v4.0-128k-Q4_K_M.gguf"
```

Do **not** `git clone` the Hugging Face repo. That can pull every quant (Q4 + Q5 + Q8 + F16, tens of GB). Download **only** the Q4_K_M file.

#### Verify on the VM

```bash
ls -lh /opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf
```

Expect **~4.7G**. If you see a few KB, it is an HTML error page:

```bash
head -c 200 /opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf
rm -f /opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf
```

Then set `HF_TOKEN` and retry Method A. Next: **§8.4** (build llama.cpp) and **§8.5** (run `llama-server`).

### 7.7 Verify the file (Windows and Linux)

Windows PowerShell:

```powershell
Get-Item C:\models\RavenX-Sec-8B-GGUF\ravenx-sec-v4.0-128k-Q4_K_M.gguf | Select-Object FullName, Length, LastWriteTime
```

`Length` should be about **5,000,000,000 bytes** (~4.7 GiB).

Windows cmd: `dir` as in §7.5. Linux: `ls -lh` as in §7.6.

If the size is ~1 KB or a few MB, you downloaded an error page — delete it and retry (often needs `HF_TOKEN`).

Expected paths used in §8:

- Windows: `C:\models\RavenX-Sec-8B-GGUF\ravenx-sec-v4.0-128k-Q4_K_M.gguf`
- Linux VM: `/opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf`

Never commit the GGUF (`*.gguf` is gitignored).

### 7.8 Download troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `hf` / `huggingface-cli` not recognized | CLI not on PATH | Use the `python -c "from huggingface_hub import hf_hub_download; ..."` one-liner in §7.4 / §7.5 / §7.6 |
| `Activate.ps1` cannot be loaded | PowerShell execution policy | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` then retry |
| `python` is the Microsoft Store stub | No real Python | Install Python 3.12 from python.org and tick **Add to PATH**, or use `py` |
| File is ~1 KB | HTML error page, not the GGUF | Delete it; set `HF_TOKEN` / `$env:HF_TOKEN`; retry `hf download` |
| Download dies at 20% | Network drop | Re-run the **same** command (`hf`, `wget -c`, `curl -C -` all resume) |
| SSH drop killed the VM download | Ran in a raw SSH shell | `tmux new -s ravenx` first, or `nohup wget -c ...` as in §7.6 |
| `No space left on device` | Disk too small | `df -h`; need ≥ 8 GB free; Vast.ai disk ≥ 40 GB |
| cmd errors on a backtick `` ` `` | Pasted a PowerShell command | Use the **§7.5** one-liners (no backticks) |
| `Invoke-WebRequest` hangs / RAM spike | Used `iwr` / `wget` alias in PowerShell | Use **`curl.exe`**, not PowerShell `wget` |

---

## 8. llama.cpp — install and run (including Windows)

**What llama.cpp is:** a C++ runtime that loads the GGUF and exposes an **OpenAI-compatible HTTP API**.

**What Xolaris needs:** the **`llama-server`** binary (not `llama-cli`). FastAPI calls:

`{LLAMA_BASE_URL}/v1/chat/completions`  
Default: `http://127.0.0.1:8080`

You need **two terminals** after this section:

1. Terminal A: `llama-server` (stays running).  
2. Terminal B: `uvicorn` for the backend.

Do **not** bind llama.cpp to `0.0.0.0` on a public VM. `--host 127.0.0.1` only.

### 8.1 Windows — install prebuilt binaries (do this locally)

You do **not** need Visual Studio or CMake on Windows. Use official zips from:

[https://github.com/ggml-org/llama.cpp/releases](https://github.com/ggml-org/llama.cpp/releases)

Open the **latest** `b#####` release. Filenames look like `llama-b10793-bin-win-….zip` (the number changes every day — take the newest).

#### Pick the zip for your hardware

| Your PC | Download this asset |
|---------|---------------------|
| **NVIDIA GPU** + CUDA 12 | `llama-bXXXXX-bin-win-cuda-12.4-x64.zip` **and** `cudart-llama-bin-win-cuda-12.4-x64.zip` |
| **NVIDIA GPU** + CUDA 13 | `llama-bXXXXX-bin-win-cuda-13.3-x64.zip` **and** `cudart-llama-bin-win-cuda-13.3-x64.zip` |
| **AMD / Intel GPU** (or NVIDIA without CUDA toolkit) | `llama-bXXXXX-bin-win-vulkan-x64.zip` |
| **CPU only** (no usable GPU) | `llama-bXXXXX-bin-win-cpu-x64.zip` |
| Snapdragon / ARM laptop | `llama-bXXXXX-bin-win-cpu-arm64.zip` |

How to choose NVIDIA CUDA 12 vs 13:

```powershell
nvidia-smi
```

If that command fails, you do **not** have a working NVIDIA driver — use **Vulkan** or **CPU**. If it works, CUDA 12.4 zip is the usual laptop choice; use 13.x only if your installed CUDA runtime is 13.

#### Extract

```powershell
New-Item -ItemType Directory -Force -Path C:\llama.cpp | Out-Null
# Expand the llama-bXXXXX-bin-win-….zip into C:\llama.cpp
# If you downloaded cudart-….zip, extract those DLLs into the SAME folder
```

In File Explorer: extract the zip into `C:\llama.cpp`. You should see **`llama-server.exe`** in that folder (sometimes in a subfolder — if so, use that subfolder as `$LlamaDir` below).

CUDA builds without the **cudart** zip often fail at start with `cudart64_*.dll was not found`. Extract the matching `cudart-llama-bin-win-cuda-….zip` **into the same directory** as `llama-server.exe`.

#### Start the server (keep this window open)

**NVIDIA (CUDA zip):**

```powershell
$LlamaDir = "C:\llama.cpp"
$Model = "C:\models\RavenX-Sec-8B-GGUF\ravenx-sec-v4.0-128k-Q4_K_M.gguf"

Set-Location $LlamaDir
.\llama-server.exe `
  -m $Model `
  --host 127.0.0.1 `
  --port 8080 `
  -c 4096 `
  -ngl 99 `
  --alias RavenX
```

**Vulkan (AMD/Intel, or NVIDIA without CUDA zip):**

Same command; if it is slow, try `-ngl 99` still (Vulkan offload). If it errors, drop to CPU (`-ngl 0`).

**CPU only:**

```powershell
$LlamaDir = "C:\llama.cpp"
$Model = "C:\models\RavenX-Sec-8B-GGUF\ravenx-sec-v4.0-128k-Q4_K_M.gguf"

Set-Location $LlamaDir
.\llama-server.exe `
  -m $Model `
  --host 127.0.0.1 `
  --port 8080 `
  -c 2048 `
  -ngl 0 `
  --threads $env:NUMBER_OF_PROCESSORS `
  --alias RavenX
```

| Flag | Meaning |
|------|---------|
| `-m` | Path to the GGUF from §7 |
| `--port 8080` | Must match `LLAMA_BASE_URL` |
| `-c` | Context window. 4096 is enough for demo. 2048 on CPU. Do **not** start at 128K. |
| `-ngl 99` | Offload as many layers as possible to GPU. `0` = CPU only. |
| `--alias RavenX` | Name FastAPI sends as `model` |
| `--host 127.0.0.1` | Only this PC can call it |

**Healthy start:** the console prints that the model loaded and it is listening on `http://127.0.0.1:8080`. Leave this window open. Ctrl+C stops the model.

First load can take 30–90 seconds (reads ~5 GB from disk).

### 8.2 Smoke-test llama.cpp (before FastAPI)

**New PowerShell window** (leave llama-server running):

```powershell
Invoke-RestMethod http://127.0.0.1:8080/v1/models
```

You should see a model list that includes `RavenX` (or the filename). Then:

```powershell
$body = @{
  model = "RavenX"
  messages = @(@{ role = "user"; content = "Say hello in one sentence." })
  max_tokens = 64
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/v1/chat/completions `
  -ContentType "application/json" `
  -Body $body
```

Success = JSON with `choices[0].message.content` containing a short reply.

Browser check: `http://127.0.0.1:8080` opens llama.cpp’s own tiny UI. That proves the server, not Xolaris.

### 8.3 Wire FastAPI (Windows local)

`backend/.env` (create if missing; **never commit**):

```
LLAMA_BASE_URL=http://127.0.0.1:8080
MODEL_NAME=RavenX
SCAN_DEFAULT_MODE=simulate
```

Start the API **in a second terminal**:

```powershell
cd C:\Users\CIGI-USER\Downloads\Autonomous-Security\backend
.\venv\Scripts\Activate.ps1
uvicorn app:app --reload
```

Then:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/chat `
  -ContentType "application/json" `
  -Body '{"message":"What is a CVE? Answer in two sentences."}'
```

Success = JSON with `data.response` containing RavenX text. If that works, local install is done.

Order every time you reboot:

1. Start `llama-server.exe` (terminal A) and wait until it is listening.  
2. Start `uvicorn` (terminal B).  
3. Call `/chat`.

### 8.4 Linux — build from source (Vast.ai / AWS)

```bash
sudo apt-get install -y build-essential cmake git
git clone https://github.com/ggml-org/llama.cpp /opt/llama.cpp
cd /opt/llama.cpp
cmake -B build -DGGML_CUDA=ON   # omit GGML_CUDA=ON for CPU-only
cmake --build build --config Release -j
```

Binary is typically `/opt/llama.cpp/build/bin/llama-server`.

### 8.5 Linux — run (NVIDIA)

```bash
export MODEL=/opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf

/opt/llama.cpp/build/bin/llama-server \
  -m "$MODEL" \
  --host 127.0.0.1 \
  --port 8080 \
  -c 8192 \
  -ngl 99 \
  --alias RavenX
```

Keep it under `tmux` or systemd. Smoke:

```bash
curl -s http://127.0.0.1:8080/v1/models
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"RavenX","messages":[{"role":"user","content":"Say hello"}]}'
```

Then the same FastAPI `.env` as §8.3 (`LLAMA_BASE_URL=http://127.0.0.1:8080`).

### 8.6 Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `Connection refused` on `:8080` | llama-server not running | Start §8.1; wait for “listening” |
| `cudart64_*.dll was not found` | CUDA zip without cudart zip | Extract matching `cudart-llama-bin-win-cuda-*.zip` next to the exe |
| `llama-server.exe` exits instantly | Wrong zip for CPU/GPU, or bad GGUF path | Check `-m` path; try CPU zip + `-ngl 0` |
| Download is 1 KB | HTML error page, not the GGUF | Delete file; set `HF_TOKEN`; use `hf download` |
| `/chat` times out (~300s) | CPU-only 8B is too slow, or `-c` too large | Use `-c 2048`, `-ngl 0`, wait; or use a GPU zip |
| Out of memory / process killed | Context or GPU layers too high | `-c 2048`, reduce `-ngl` (try `20` then `40`) |
| Port 8080 already in use | Another llama / Ollama / app | `netstat -ano \| findstr :8080` or use `--port 8081` **and** change `LLAMA_BASE_URL` |
| Chat works in browser `:8080` but FastAPI fails | Wrong `.env` or uvicorn started before server | Confirm `.env` in `backend/`; restart uvicorn |
| You ran `llama-cli.exe` | CLI is one-shot, no HTTP API | You need **`llama-server.exe`** |

---


## 9. Security tools (adapters)

Adapters expect the binary **on PATH** (`binary_path` defaults: `nuclei`, `trivy`, …). Install on the **same Linux VM** as FastAPI.

### 9.1 This month (must)

**Nuclei** — web/network vulns.

```bash
# Go install (needs Go) or GitHub release
curl -sL "https://github.com/projectdiscovery/nuclei/releases/latest/download/nuclei_$(uname -s)_amd64.zip" -o /tmp/nuclei.zip
# If the asset name differs, download from https://github.com/projectdiscovery/nuclei/releases
sudo apt-get install -y unzip
# Example with go:
sudo apt-get install -y golang-go
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
export PATH="$PATH:$(go env GOPATH)/bin"
nuclei -update-templates
nuclei -version
```

**Trivy** — image / FS vulns.

```bash
sudo apt-get install -y wget apt-transport-https gnupg lsb-release
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
echo deb https://aquasecurity.github.io/trivy-repo/deb "$(lsb_release -sc)" main | sudo tee /etc/apt/sources.list.d/trivy.list
sudo apt-get update && sudo apt-get install -y trivy
trivy --version
```

Live scan examples (only on hosts you are allowed to test):

```json
{ "tenant_id": "00000000-0000-4000-8000-000000000001", "target": "https://your-lab.example", "tool_name": "nuclei", "mode": "live", "run_pipeline": true }
```

```json
{ "tenant_id": "00000000-0000-4000-8000-000000000001", "target": "alpine:3.20", "tool_name": "trivy", "mode": "live", "run_pipeline": true }
```

Use a **lab target**. Do not scan third-party production without authorization.

### 9.2 If time remains in week 2

| Tool | Typical install | Use |
|------|-----------------|-----|
| **Prowler** | `pip install prowler` | AWS account checks (needs AWS creds) |
| **Checkov** | `pip install checkov` | IaC (`checkov -d .`) |
| **Grype** | [Anchore install script](https://github.com/anchore/grype#installation) | Image CVEs |

Code adapters already exist under `backend/src/adapters/`.

### 9.3 Not this month

Gitleaks, ZAP, OSV, Semgrep — backlog 4.8.

---

## 10. Environment variables

Create `backend/.env` on the VM (chmod 600).

```
APP_NAME=Xolaris
HOST=0.0.0.0
PORT=8000
LLAMA_BASE_URL=http://127.0.0.1:8080
MODEL_NAME=RavenX
DATABASE_URL=postgresql+psycopg://xolaris:CHANGE_ME@127.0.0.1:5432/xolaris
CREATE_TABLES=true
DECISION_ENABLE_AI_STACK=false
LLM_ENABLE_V2_STACK=true
SCAN_DEFAULT_MODE=live
SCAN_ENABLE_CHAT_TOOLS=true
SCAN_DEFAULT_TENANT_ID=00000000-0000-4000-8000-000000000001
SCAN_CHAT_RUN_PIPELINE=true
```

Local Windows: omit Postgres, keep `SCAN_DEFAULT_MODE=simulate`, follow **§7.4 or §7.5 + §8.1–8.3** for chat. `LLAMA_BASE_URL` stays `http://127.0.0.1:8080`.

Demo tenant UUID is stable in config: `00000000-0000-4000-8000-000000000001`.

---

## 11. Deployment — Vast.ai (preferred for this month)

Cheapest path for a GPU + Linux. Week 1 of the LOE.

### 11.1 Rent the instance

1. Create account at [vast.ai](https://vast.ai).  
2. Filter: **Ubuntu 22.04**, NVIDIA GPU with **≥ 12 GB VRAM** (24 GB is safer), ≥ 40 GB disk, CUDA.  
3. Template: PyTorch or CUDA devel image is fine; you will install llama.cpp yourself.  
4. Note **SSH** host/port/user from the instance page.  
5. Cost: leave on only while demos run (~USD 0.3–1.5/hr typical).

### 11.2 First SSH

```bash
ssh -p <PORT> root@<HOST>
nvidia-smi
df -h
```

### 11.3 Install stack (order)

1. System packages: `git`, `python3.12-venv`, `python3-pip`, `docker.io`, `docker-compose-plugin`, `build-essential`, `cmake`.  
2. Download GGUF (**§7.6** — Hugging Face CLI, `wget`, `curl`, or `aria2c`; use `tmux` so SSH drop does not kill it).  
3. Build llama.cpp with CUDA (§8.4–8.5); start `llama-server` in `tmux`.  
4. Clone this repo (`git clone` `dev` branch).  
5. `cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.  
6. `docker compose up -d` for Postgres; set `DATABASE_URL` in `.env`.  
7. Install Nuclei + Trivy (section 9).  
8. `uvicorn app:app --host 0.0.0.0 --port 8000`.  
9. **Do not** leave 8000 open to the world until API keys (week 4). Use SSH tunnel:

```powershell
ssh -p <PORT> -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 root@<HOST>
```

Then on your laptop: `http://localhost:8000/docs`.

### 11.4 Firewall

- llama.cpp: **localhost only**.  
- FastAPI: tunnel until keys exist; later bind 8000 behind a reverse proxy.  
- Postgres: **localhost only** (already mapped 5432 in compose — do not publish 5432 to the public internet on Vast).

Change compose if needed: remove host `ports` and use a Docker network only.

---

## 12. Deployment — AWS (alternative)

Use AWS if the company requires it. **More expensive** than Vast.ai for GPU.

### 12.1 Suggested layout

| Piece | AWS service | Notes |
|-------|-------------|--------|
| GPU inference | EC2 `g5.xlarge` or `g6.xlarge` (NVIDIA) | Same llama.cpp + GGUF as Vast |
| Or split | CPU `t3.large` for FastAPI+Postgres, GPU instance only for llama.cpp | More moving parts; skip in 22 days |
| Disk | 50+ GB gp3 | GGUF + templates |
| DB | RDS Postgres 16 **or** Docker Postgres on the same EC2 | RDS is cleaner; Docker matches current compose |
| SSH | SSM Session Manager or key pair | Prefer SSM |
| HTTPS | ALB + ACM (week 4+; **out of this month** except a self-signed nginx if demanded) |

### 12.2 EC2 steps (same software as Vast)

1. Ubuntu 22.04 AMI, GPU instance, IAM role if using SSM.  
2. Security group: **22 (or SSM only)** from your IP; **no 8080/5432**. 8000 only after API keys, from office IP or ALB.  
3. Repeat sections 7–9 and 11.3.  
4. Elastic IP if the instance must keep an address.

### 12.3 Do not do this month

EKS, Lambda, SageMaker endpoints, Bedrock. The app is FastAPI + llama.cpp on one box.

---

## 13. HTTP catalog (already mounted)

Prefix `/api/v1` unless noted.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/chat` | RavenX chat (needs llama.cpp) |
| POST | `/chat/stream` | SSE stream |
| GET | `/health` | Liveness |
| POST | `/api/v1/scans` | Scan + ingest + optional pipeline |
| GET | `/api/v1/findings` | Search findings |
| GET | `/api/v1/findings/{id}` | Finding + evidence |
| GET | `/api/v1/findings/{id}/history` | History |
| GET | `/api/v1/assets` | Search assets |
| GET | `/api/v1/assets/{id}` | One asset |
| POST/GET | `/api/v1/trust/*` | Trust scoring |
| POST/GET | `/api/v1/risk/*` | Risk scoring |
| POST/GET | `/api/v1/decisions/*` | Decisions |
| POST/GET | `/api/v1/remediation-plans/*` | Plans |
| POST/GET | `/api/v1/simulations/*` | Simulation |
| POST/GET | `/api/v1/approvals/*` | Approvals |
| POST/GET | `/api/v1/executions/*` | Execution (recording adapter) |
| POST/GET | `/api/v1/verifications/*` | Verification |
| POST/GET | `/api/v1/reporting/*` | Reports |
| POST/GET | `/api/v1/ai-harness/*` | AI harness |

Swagger: `http://localhost:8000/docs`.

---

## 14. Next tasks — how to implement (Feature 4.7)

Follow the LOE weeks. Implementation notes are **where to change code**, not a rewrite.

### Week 1 — Host (5 days)

| ID | Task | How |
|----|------|-----|
| W1.1 | GPU VM | Vast.ai first; AWS only if mandated. SSH, `nvidia-smi`. |
| W1.2 | RavenX | §7. Windows laptop: **PowerShell §7.4** or **CMD §7.5**. GPU VM: **§7.6**. Q4_K_M. Confirm ~4.7 GB. |
| W1.3 | llama.cpp | §8. Windows: **prebuilt zip + `llama-server.exe` (§8.1–8.3)**. Linux VM: build §8.4, run §8.5. Prove `/v1/models`. |
| W1.4 | Backend | Clone `dev`, venv, `requirements.txt`, `.env`, `uvicorn`. **Exit:** `POST /chat` returns RavenX text. |

No application code required if `.env` is correct.

### Week 2 — Scanners + DB (5 days)

| ID | Task | How |
|----|------|-----|
| W2.1 | Nuclei + Trivy | Section 9. `which nuclei trivy`. |
| W2.2 | Smoke | `mode: live` on a **lab** target; then `GET /findings`. Chat: `scan https://lab…`. |
| W2.3 | Postgres | `docker compose up -d` in `backend/`. Set `DATABASE_URL`. `CREATE_TABLES=true`. **No Alembic this month.** Restart API; scan again; restart API; findings still listed. |

If week 2 slips: stay on simulate + SQLite and **say so**; do not fake live scans.

### Week 3 — Persist + test (6 days)

**W3.1 Multi-tenant check**

- Two `tenant_id` values; scan A then B.  
- `GET /findings` for A must not include B.  
- `pg_dump` once to a file on the VM (ops, not new engine).

**W3.2 Persistent chat memory**

Today: `backend/services/memory_service.py` — `defaultdict` in process.

Implement:

1. Table e.g. `chat_messages (tenant_id, session_id, role, content, created_at)`.  
2. New `PostgresMemoryService` with the same methods: `get_history`, `add_user_message`, `add_assistant_message`, `clear`.  
3. Wire it in `get_llm_service()` in `backend/api/deps.py` instead of `MemoryService()`.  
4. Keep `max_messages = 20` trim.  
5. Test: two `/chat` calls, kill uvicorn, third call still has history.

Do not put secrets in messages logs.

**W3.3 E2E happy path**

Script (pytest or unittest + TestClient / httpx against a running server):

1. `POST /scans` simulate or live.  
2. Assert findings ≥ 1.  
3. `GET /trust/findings/{id}` and `/risk/findings/{id}` if pipeline ran.  
4. Decision + plan IDs present on scan `pipeline` payload.  
5. Do **not** require execute/verify/report this month.

Put tests in `backend/tests/test_e2e_happy_path.py`.

### Week 4 — Demo lock (6 days)

**W4.1 API keys (not JWT)**

1. Setting `API_KEYS=dev-key-one,dev-key-two` in `.env`.  
2. Middleware or dependency: require header `X-API-Key` on `/api/v1/*` and `/chat`.  
3. Allow `/health` without a key.  
4. 401 if missing/wrong.  
5. Document the header in `/docs` (FastAPI security scheme).

**W4.2 Auto simulation + submit approval**

File: `backend/scan_ingest/services/finding_pipeline.py` after a plan is saved.

1. Reuse `SimulationEngineContainer` / `ApprovalEngineContainer` the same way scan ingest already pulls trust/risk/decision/planner in `ScanIngestContainer`.  
2. Map plan snapshot into existing `Simulation` request models (see `backend/api/v1/simulations.py` and tests).  
3. On simulation success, create an approval in **pending** state — **do not** auto-approve, **do not** call execution.  
4. Return `simulation_id` and `approval_id` on `PipelineFindingResult` (extend that model).  
5. Unit test with in-memory/sqlite containers like `test_scan_ingest.py`.

**W4.3 Findings list on real API**

File: `frontend/src/pages/FindingsPage.tsx` (and types).

1. `fetch('http://localhost:8000/api/v1/findings?tenant_id=' + DEMO_TENANT)` with `X-API-Key`.  
2. Keep layout; swap mock `FINDINGS` array.  
3. Empty and error states.  
4. CORS already includes 5173; add the Vast tunnel origin if the UI is opened from another host.  
5. Rehearse a 10-minute demo: chat → scan → findings list → one finding → mention plan/simulation/approval IDs.

### Planner mapping

- **4.5** Reporting — done.  
- **4.6** Findings/Assets APIs — done.  
- **4.7** This file — 22 days.  
- **4.8** Backlog — no dates until 4.7 is done.

---

## 15. Out of this month (do not start)

Alembic · JWT/OIDC · full React · async `GET /scans/{id}` · CISA KEV/NVD live feeds · OPA · OpenAI/Anthropic · RAG · real SSH/cloud execute · Gitleaks/ZAP/OSV/Semgrep · MCP tools · production nginx/TLS platform logging.

If asked to “just add RAG” during 4.7, refuse and point here.

---

## 16. Demo script (10 minutes)

1. `GET /health`.  
2. `POST /chat` — “Explain why OpenSSH 7.4 is risky” (RavenX RATH-style answer).  
3. `POST /api/v1/scans` `mode: simulate` (or live lab) `run_pipeline: true`.  
4. `GET /api/v1/findings?tenant_id=…`.  
5. Open one finding; show trust/risk/plan IDs if present.  
6. After W4.2: show pending approval.  
7. Restart uvicorn; findings still there (Postgres).  
8. Call an API **without** key → 401.

---

## 17. Risks

| Risk | Mitigation |
|------|------------|
| Vast.ai GPU gone / preempted | Snapshot disk; keep GGUF on `/opt/models`; budget AWS g5 as fallback |
| Hugging Face slow | `wget -c` / `aria2c` / `hf download` (all resume); start on day 1 inside `tmux` |
| CUDA build fails | CPU llama.cpp works but is slow; say it in the demo |
| Live scan of unauthorized host | Lab targets only |
| 8000 exposed without keys | SSH tunnel until W4.1 |
| 83-day backlog confusion | This month is **22 days**; full list is 4.8 |

---

## 18. Related docs

| Doc | Use |
|-----|-----|
| [docs/planning/Xolaris-LOE-1-Month.html](docs/planning/Xolaris-LOE-1-Month.html) | Calendar and day estimates |
| [docs/architecture/README.md](docs/architecture/README.md) | Module contracts |
| [docs/adapters/README.md](docs/adapters/README.md) | Add a scanner |
| [backend/scan_ingest/README.md](backend/scan_ingest/README.md) | Scan orchestrator |
| [docs/architecture/22-scan-ingest.md](docs/architecture/22-scan-ingest.md) | Scan sequence |
| Hugging Face | [RavenX-Sec-8B-GGUF](https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF) |
