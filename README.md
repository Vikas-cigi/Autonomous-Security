# Autonomous Security (Xolaris)

Enterprise autonomous cybersecurity remediation control plane — Python backend + React prototype frontend.

## Repository layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI app, engines, adapters, scan/ingest |
| `frontend/` | Vite + React prototype (mock data; API wiring in progress) |
| `docs/` | Architecture and adapter plugin guides |

## Quick start (backend)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Copy settings from team lead — do not commit .env
uvicorn app:app --reload
```

API docs: `http://localhost:8000/docs`

Default persistence: SQLite (`sqlite+pysqlite:///./xolaris.db`). No separate DB install required for local dev.

## Pipeline

```
Scan/Ingest → Evidence → Trust → Risk → Decision → Plan
→ Simulation → Approval → Execution → Verification → Reporting
```

## Key docs

- [Architecture index](docs/architecture/README.md)
- [Adapter plugin guide](docs/adapters/README.md)
- [Scan / Ingest](backend/scan_ingest/README.md)

## Adapters (built-in)

`nuclei`, `trivy`, `prowler`, `checkov`, `grype` — see `backend/src/adapters/`.

Simulate scans work without installing scanner binaries (`POST /api/v1/scans` with `"mode": "simulate"`).

After a scan, list persisted records:

- `GET /api/v1/findings?tenant_id=`
- `GET /api/v1/assets?tenant_id=`
