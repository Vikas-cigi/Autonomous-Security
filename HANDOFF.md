# Xolaris handoff

**Audience:** next engineer taking Feature **4.7 One-Month Go-Live** (22 working days).  
**Source plan:** [docs/planning/Xolaris-LOE-1-Month.html](docs/planning/Xolaris-LOE-1-Month.html) (also `.docx` / `.pdf` in the same folder).  
**Repo:** `https://github.com/Vikas-cigi/Autonomous-Security` · branch `dev`.  
**Do not rebuild engines.** Host them, persist data, prove a live demo.

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

---

## 2. Architecture

Canonical module docs: [docs/architecture/README.md](docs/architecture/README.md).

### 2.1 Control-plane pipeline

```
Scan/Ingest → Evidence → Trust → Risk → Decision → Plan
          → Simulation → Approval → Execution → Verification → Reporting
```

Today `FindingPipelineService` (`backend/scan_ingest/services/finding_pipeline.py`) stops at **Plan**. Simulation and Approval exist as APIs but are **not auto-chained**. That chain is a week-4 task.

### 2.2 Platform map

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

### 2.3 Runtime (what you actually start)

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

### 2.4 Module status (do not rebuild Done)

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

## 3. Repository map

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

## 4. How a request works (detail)

### 4.1 Chat

1. Client `POST /chat` with `{ "message": "...", "session_id": "optional" }`.  
2. If the message looks like a scan (`scan https://…`), intent is `TOOL` and `ScanToolBuilder` runs the same scan orchestrator.  
3. Otherwise the LLM answers using RavenX (once llama.cpp is up).  
4. **Today** history is **in RAM** (`MemoryService`, last 20 messages). Restart wipes chat. Week 3 replaces this with Postgres.

### 4.2 Scan

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

### 4.3 Findings after scan

Use the **same** `tenant_id`:

```http
GET /api/v1/findings?tenant_id=00000000-0000-4000-8000-000000000001
GET /api/v1/findings/{finding_id}?tenant_id=...
GET /api/v1/findings/{finding_id}/history?tenant_id=...
GET /api/v1/assets?tenant_id=...
```

Wrong tenant → not-found envelope (`success: false`), not another tenant’s rows.

---

## 5. Local testing (Windows laptop)

You can prove the **control plane without GPU** using simulate mode + SQLite.

### 5.1 Prerequisites

- Python 3.11 or 3.12 on PATH (not the Microsoft Store stub).  
- Git.  
- Optional: Docker Desktop if you want Postgres locally.  
- Optional: Node 20+ for the frontend.  
- llama.cpp + GGUF are **optional** locally; chat will fail until `:8080` is up.

### 5.2 Backend

```powershell
cd C:\Users\CIGI-USER\Downloads\Autonomous-Security\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Open `http://localhost:8000/docs`.

Health: `GET http://localhost:8000/health` → `{ "status": "healthy" }`.

### 5.3 Simulate scan (no scanner binaries)

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

### 5.4 Unit tests

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
python -m unittest tests.test_findings_assets_api tests.test_scan_ingest -v
```

### 5.5 Optional local Postgres

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

### 5.6 Optional local chat (if you have a GGUF + llama.cpp on Windows)

Set:

```
LLAMA_BASE_URL=http://127.0.0.1:8080
MODEL_NAME=RavenX
```

Then:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/chat" -ContentType "application/json" -Body '{"message":"What is a CVE?"}'
```

### 5.7 Frontend (mock only)

```powershell
cd frontend
npm install
npm run dev
```

`http://localhost:5173` — dummy data. CORS already allows 5173. Week 4: replace findings page `fetch` only.

---

## 6. RavenX model download

**Repo:** [https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF](https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF)

This is **GGUF** for llama.cpp / Ollama / LM Studio. Architecture: **Qwen3-8B**, 128K context, Apache-2.0. Built for find → classify → fix → verify → report (RATH protocol).

### 6.1 Which file to use

| File | Quant | Disk | Typical VRAM | When |
|------|-------|------|--------------|------|
| **`ravenx-sec-v4.0-128k-Q4_K_M.gguf`** | Q4_K_M | **4.7 GB** | ~6–8 GB | **Default for Vast.ai** |
| `ravenx-sec-v4.0-128k-Q5_K_M.gguf` | Q5_K_M | 5.4 GB | ~8–10 GB | If VRAM ≥ 12 GB |
| `ravenx-sec-v4.0-128k-Q8_0.gguf` | Q8_0 | 8.1 GB | ~10–12 GB | Quality over cost |
| `ravenx-sec-v4.0-128k-f16.gguf` | F16 | 15.3 GB | ~16 GB+ | Do not use on cheap GPUs |

**Recommend Q4_K_M** for the 1-month demo.

Ollama shortcut (optional, not required by our backend):

```bash
ollama run hf.co/deadbydawn101/RavenX-Sec-8B-GGUF:ravenx-sec-v4.0-128k-Q8_0
```

The FastAPI app talks to **llama.cpp OpenAI server**, not Ollama, unless you point `LLAMA_BASE_URL` at Ollama’s OpenAI-compatible port. Prefer llama.cpp as documented below.

### 6.2 Download on Linux (Vast.ai / AWS)

```bash
sudo apt-get update && sudo apt-get install -y python3-pip git wget
pip install -U "huggingface_hub[cli]"

mkdir -p /opt/models && cd /opt/models
huggingface-cli download deadbydawn101/RavenX-Sec-8B-GGUF \
  ravenx-sec-v4.0-128k-Q4_K_M.gguf \
  --local-dir /opt/models/RavenX-Sec-8B-GGUF
```

Direct URL (same file):

```bash
wget -c "https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF/resolve/main/ravenx-sec-v4.0-128k-Q4_K_M.gguf" \
  -O /opt/models/ravenx-sec-v4.0-128k-Q4_K_M.gguf
```

If the CLI asks for a token, create a **read** token at huggingface.co/settings/tokens (public repo usually works without it).

Checksum: after download, confirm size is about **4.7 GB**. Do not commit the GGUF into git.

---

## 7. llama.cpp (required for `/chat`)

Backend calls: `{LLAMA_BASE_URL}/v1/chat/completions`  
Default: `http://127.0.0.1:8080`.

### 7.1 Build

```bash
sudo apt-get install -y build-essential cmake git
git clone https://github.com/ggml-org/llama.cpp /opt/llama.cpp
cd /opt/llama.cpp
cmake -B build -DGGML_CUDA=ON   # use GGML_HIPBLAS or CPU-only if no NVIDIA
cmake --build build --config Release -j
```

Binary is typically `build/bin/llama-server`.

### 7.2 Run (NVIDIA example)

```bash
export MODEL=/opt/models/RavenX-Sec-8B-GGUF/ravenx-sec-v4.0-128k-Q4_K_M.gguf
# if wget'd to /opt/models/*.gguf, use that path

/opt/llama.cpp/build/bin/llama-server \
  -m "$MODEL" \
  --host 127.0.0.1 \
  --port 8080 \
  -c 8192 \
  -ngl 99 \
  --alias RavenX
```

| Flag | Meaning |
|------|---------|
| `-c 8192` | Context; raise later if VRAM allows (model supports 128K; 8K is enough for demo) |
| `-ngl 99` | Offload all layers to GPU |
| `--host 127.0.0.1` | Only FastAPI on the same VM talks to it. Do not expose 8080 to the internet. |

Keep it running under `tmux` or systemd. Smoke:

```bash
curl -s http://127.0.0.1:8080/v1/models
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"RavenX","messages":[{"role":"user","content":"Say hello"}]}'
```

Then FastAPI `.env`:

```
LLAMA_BASE_URL=http://127.0.0.1:8080
MODEL_NAME=RavenX
```

---

## 8. Security tools (adapters)

Adapters expect the binary **on PATH** (`binary_path` defaults: `nuclei`, `trivy`, …). Install on the **same Linux VM** as FastAPI.

### 8.1 This month (must)

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

### 8.2 If time remains in week 2

| Tool | Typical install | Use |
|------|-----------------|-----|
| **Prowler** | `pip install prowler` | AWS account checks (needs AWS creds) |
| **Checkov** | `pip install checkov` | IaC (`checkov -d .`) |
| **Grype** | [Anchore install script](https://github.com/anchore/grype#installation) | Image CVEs |

Code adapters already exist under `backend/src/adapters/`.

### 8.3 Not this month

Gitleaks, ZAP, OSV, Semgrep — backlog 4.8.

---

## 9. Environment variables

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

Local Windows without GPU: omit Postgres, keep `SCAN_DEFAULT_MODE=simulate`, no `LLAMA_BASE_URL` change until llama.cpp exists.

Demo tenant UUID is stable in config: `00000000-0000-4000-8000-000000000001`.

---

## 10. Deployment — Vast.ai (preferred for this month)

Cheapest path for a GPU + Linux. Week 1 of the LOE.

### 10.1 Rent the instance

1. Create account at [vast.ai](https://vast.ai).  
2. Filter: **Ubuntu 22.04**, NVIDIA GPU with **≥ 12 GB VRAM** (24 GB is safer), ≥ 40 GB disk, CUDA.  
3. Template: PyTorch or CUDA devel image is fine; you will install llama.cpp yourself.  
4. Note **SSH** host/port/user from the instance page.  
5. Cost: leave on only while demos run (~USD 0.3–1.5/hr typical).

### 10.2 First SSH

```bash
ssh -p <PORT> root@<HOST>
nvidia-smi
df -h
```

### 10.3 Install stack (order)

1. System packages: `git`, `python3.12-venv`, `python3-pip`, `docker.io`, `docker-compose-plugin`, `build-essential`, `cmake`.  
2. Download GGUF (section 6).  
3. Build llama.cpp with CUDA (section 7); start `llama-server` in `tmux`.  
4. Clone this repo (`git clone` `dev` branch).  
5. `cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.  
6. `docker compose up -d` for Postgres; set `DATABASE_URL` in `.env`.  
7. Install Nuclei + Trivy (section 8).  
8. `uvicorn app:app --host 0.0.0.0 --port 8000`.  
9. **Do not** leave 8000 open to the world until API keys (week 4). Use SSH tunnel:

```powershell
ssh -p <PORT> -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 root@<HOST>
```

Then on your laptop: `http://localhost:8000/docs`.

### 10.4 Firewall

- llama.cpp: **localhost only**.  
- FastAPI: tunnel until keys exist; later bind 8000 behind a reverse proxy.  
- Postgres: **localhost only** (already mapped 5432 in compose — do not publish 5432 to the public internet on Vast).

Change compose if needed: remove host `ports` and use a Docker network only.

---

## 11. Deployment — AWS (alternative)

Use AWS if the company requires it. **More expensive** than Vast.ai for GPU.

### 11.1 Suggested layout

| Piece | AWS service | Notes |
|-------|-------------|--------|
| GPU inference | EC2 `g5.xlarge` or `g6.xlarge` (NVIDIA) | Same llama.cpp + GGUF as Vast |
| Or split | CPU `t3.large` for FastAPI+Postgres, GPU instance only for llama.cpp | More moving parts; skip in 22 days |
| Disk | 50+ GB gp3 | GGUF + templates |
| DB | RDS Postgres 16 **or** Docker Postgres on the same EC2 | RDS is cleaner; Docker matches current compose |
| SSH | SSM Session Manager or key pair | Prefer SSM |
| HTTPS | ALB + ACM (week 4+; **out of this month** except a self-signed nginx if demanded) |

### 11.2 EC2 steps (same software as Vast)

1. Ubuntu 22.04 AMI, GPU instance, IAM role if using SSM.  
2. Security group: **22 (or SSM only)** from your IP; **no 8080/5432**. 8000 only after API keys, from office IP or ALB.  
3. Repeat sections 6–8 and 10.3.  
4. Elastic IP if the instance must keep an address.

### 11.3 Do not do this month

EKS, Lambda, SageMaker endpoints, Bedrock. The app is FastAPI + llama.cpp on one box.

---

## 12. HTTP catalog (already mounted)

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

## 13. Next tasks — how to implement (Feature 4.7)

Follow the LOE weeks. Implementation notes are **where to change code**, not a rewrite.

### Week 1 — Host (5 days)

| ID | Task | How |
|----|------|-----|
| W1.1 | GPU VM | Vast.ai first; AWS only if mandated. SSH, `nvidia-smi`. |
| W1.2 | RavenX | Section 6. Q4_K_M. Confirm ~4.7 GB. |
| W1.3 | llama.cpp | Section 7. systemd or tmux. Curl `/v1/models`. |
| W1.4 | Backend | Clone `dev`, venv, `requirements.txt`, `.env`, `uvicorn`. **Exit:** `POST /chat` returns RavenX text. |

No application code required if `.env` is correct.

### Week 2 — Scanners + DB (5 days)

| ID | Task | How |
|----|------|-----|
| W2.1 | Nuclei + Trivy | Section 8. `which nuclei trivy`. |
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

## 14. Out of this month (do not start)

Alembic · JWT/OIDC · full React · async `GET /scans/{id}` · CISA KEV/NVD live feeds · OPA · OpenAI/Anthropic · RAG · real SSH/cloud execute · Gitleaks/ZAP/OSV/Semgrep · MCP tools · production nginx/TLS platform logging.

If asked to “just add RAG” during 4.7, refuse and point here.

---

## 15. Demo script (10 minutes)

1. `GET /health`.  
2. `POST /chat` — “Explain why OpenSSH 7.4 is risky” (RavenX RATH-style answer).  
3. `POST /api/v1/scans` `mode: simulate` (or live lab) `run_pipeline: true`.  
4. `GET /api/v1/findings?tenant_id=…`.  
5. Open one finding; show trust/risk/plan IDs if present.  
6. After W4.2: show pending approval.  
7. Restart uvicorn; findings still there (Postgres).  
8. Call an API **without** key → 401.

---

## 16. Risks

| Risk | Mitigation |
|------|------------|
| Vast.ai GPU gone / preempted | Snapshot disk; keep GGUF on `/opt/models`; budget AWS g5 as fallback |
| Hugging Face slow | `wget -c`; start download on day 1 |
| CUDA build fails | CPU llama.cpp works but is slow; say it in the demo |
| Live scan of unauthorized host | Lab targets only |
| 8000 exposed without keys | SSH tunnel until W4.1 |
| 83-day backlog confusion | This month is **22 days**; full list is 4.8 |

---

## 17. Related docs

| Doc | Use |
|-----|-----|
| [docs/planning/Xolaris-LOE-1-Month.html](docs/planning/Xolaris-LOE-1-Month.html) | Calendar and day estimates |
| [docs/architecture/README.md](docs/architecture/README.md) | Module contracts |
| [docs/adapters/README.md](docs/adapters/README.md) | Add a scanner |
| [backend/scan_ingest/README.md](backend/scan_ingest/README.md) | Scan orchestrator |
| [docs/architecture/22-scan-ingest.md](docs/architecture/22-scan-ingest.md) | Scan sequence |
| Hugging Face | [RavenX-Sec-8B-GGUF](https://huggingface.co/deadbydawn101/RavenX-Sec-8B-GGUF) |
