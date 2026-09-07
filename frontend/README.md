# Xolaris Frontend Prototype (mock)

Shareable React UI to demo the Xolaris control plane **without** calling the FastAPI backend yet.

## Quick start

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## What is included

| Route | Purpose |
|-------|---------|
| `/` | Operations dashboard (KPIs) |
| `/findings` | Mock Nuclei findings list |
| `/findings/:id` | Trust / risk / decision detail |
| `/plans/plan-5001` | Remediation Planner output (steps + rollback) |
| `/pipeline` | Clickable Decision → … → Reporting flow |
| `/approvals` | Approve/reject (updates pipeline mock state) |
| `/chat` | Scripted RavenX replies (no LLM) |

## Important for frontend engineers

- **All data is mock** under `src/mocks/`.
- Interactive state lives in `src/state/DemoContext.tsx`.
- When wiring the real API, replace mocks with `fetch` to:
  - `/api/v1/findings`
  - `/api/v1/assets`
  - `/api/v1/trust`
  - `/api/v1/risk`
  - `/api/v1/decisions`
  - `/api/v1/remediation-plans`
  - `/api/v1/simulations`
  - `/api/v1/approvals`
  - `/api/v1/executions`
  - `/api/v1/verifications`
  - `/api/v1/reporting/*`
  - `/chat` (LLMService)

Keep screen structure; swap data source only.

## Demo walkthrough (3–5 min)

1. Dashboard → open findings  
2. Finding `fnd-1001` → trust/risk/decision  
3. Remediation Plan → steps + rollback  
4. Approvals → **Approve** OpenSSH plan  
5. Pipeline → **Advance stage** through execution → verification  
6. Chat → try a starter prompt  

## Stack

- Vite + React 19 + TypeScript  
- React Router 7  
- No backend dependency for this prototype  
