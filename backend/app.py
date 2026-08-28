from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1 import (
    ai_harness_router,
    approvals_router,
    chat_router,
    decisions_router,
    execution_router,
    health_router,
    remediation_plans_router,
    reporting_router,
    risk_router,
    scan_router,
    simulations_router,
    trust_router,
    verification_router,
)

app = FastAPI(
    title="Xolaris Cyber AI Platform",
    version="1.2.0",
    description=(
        "Enterprise autonomous remediation control plane. "
        "Chat uses LLMService (DecisionEngine → Context → Prompt → Providers) "
        "with optional Scan TOOL wiring. "
        "POST /api/v1/scans runs adapter→normalize→evidence→pipeline. "
        "Trust through Reporting are deterministic (or optionally AI-assisted) engines."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chat (LLMService V2 stack by default)
app.include_router(chat_router)

# Enterprise engines under /api/v1
_API_V1 = "/api/v1"
app.include_router(health_router, prefix=_API_V1)
app.include_router(scan_router, prefix=_API_V1)
app.include_router(trust_router, prefix=_API_V1)
app.include_router(risk_router, prefix=_API_V1)
app.include_router(decisions_router, prefix=_API_V1)
app.include_router(remediation_plans_router, prefix=_API_V1)
app.include_router(simulations_router, prefix=_API_V1)
app.include_router(approvals_router, prefix=_API_V1)
app.include_router(execution_router, prefix=_API_V1)
app.include_router(verification_router, prefix=_API_V1)
app.include_router(reporting_router, prefix=_API_V1)
app.include_router(ai_harness_router, prefix=_API_V1)


@app.get("/")
async def root():
    return {
        "message": "Xolaris Cyber AI Platform API",
        "docs": "/docs",
        "enterprise": _API_V1,
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
