"""Shared FastAPI dependencies for enterprise engine routers."""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Callable, TypeVar

from fastapi import HTTPException

from core.config import settings

T = TypeVar("T")


@lru_cache
def get_trust_container():
    from trust_scoring import TrustScoringContainer

    return TrustScoringContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_risk_container():
    from risk_engine import RiskEngineContainer

    return RiskEngineContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_decision_container():
    from decision_service import DecisionServiceContainer

    return DecisionServiceContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
        enable_ai_stack=settings.DECISION_ENABLE_AI_STACK,
    )


@lru_cache
def get_planner_container():
    from remediation_planner import RemediationPlannerContainer

    return RemediationPlannerContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_simulation_container():
    from simulation_engine import SimulationEngineContainer

    return SimulationEngineContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_approval_container():
    from approval_engine import ApprovalEngineContainer

    return ApprovalEngineContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_execution_container():
    from execution_engine import ExecutionEngineContainer

    return ExecutionEngineContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_verification_container():
    from verification_engine import VerificationEngineContainer

    return VerificationEngineContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_reporting_container():
    from reporting_analytics import ReportingAnalyticsContainer

    return ReportingAnalyticsContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_ai_harness_container():
    from ai_harness import AIHarnessContainer

    return AIHarnessContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_evidence_container():
    from evidence_repository import EvidenceRepositoryContainer

    return EvidenceRepositoryContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_asset_container():
    from asset_inventory import AssetInventoryContainer

    return AssetInventoryContainer.from_url(
        settings.DATABASE_URL,
        create_tables=settings.CREATE_TABLES,
    )


@lru_cache
def get_scan_ingest_container():
    """Scan / Ingest orchestrator with optional finding pipeline engines."""
    from scan_ingest import ScanIngestContainer

    return ScanIngestContainer(
        get_asset_container(),
        get_evidence_container(),
        trust_container=get_trust_container(),
        risk_container=get_risk_container(),
        decision_container=get_decision_container(),
        planner_container=get_planner_container(),
    )


@lru_cache
def get_llm_service():
    """Shared LLMService (V2 stack when LLM_ENABLE_V2_STACK is True)."""
    from services.llm_service import LLMService

    if not settings.LLM_ENABLE_V2_STACK or not settings.SCAN_ENABLE_CHAT_TOOLS:
        return LLMService(enable_v2_stack=settings.LLM_ENABLE_V2_STACK)

    from uuid import UUID

    from context.builders.conversation_builder import ConversationBuilder
    from context.builders.memory_builder import MemoryBuilder
    from context.builders.profile_builder import ProfileBuilder
    from context.builders.rag_builder import RAGBuilder
    from context.context_manager import ContextManager
    from decision_engine import DecisionEngine
    from scan_ingest import ScanAwareIntentRouter, ScanMode, ScanToolBuilder
    from services.memory_service import MemoryService

    memory = MemoryService()
    mode = ScanMode(settings.SCAN_DEFAULT_MODE.lower())
    tenant_id = UUID(settings.SCAN_DEFAULT_TENANT_ID)

    async def _chat_scan_runner(request):
        container = get_scan_ingest_container()
        with container.session_scope(enable_pipeline=request.run_pipeline) as svc:
            return await svc.engine.scan_async(request)

    tool_builder = ScanToolBuilder(
        scan_runner=_chat_scan_runner,
        default_tenant_id=tenant_id,
        default_mode=mode,
        run_pipeline=settings.SCAN_CHAT_RUN_PIPELINE,
    )
    context_manager = ContextManager(
        builders=[
            ConversationBuilder(memory_service=memory),
            MemoryBuilder(),
            RAGBuilder(),
            ProfileBuilder(),
            tool_builder,
        ]
    )
    return LLMService(
        enable_v2_stack=True,
        decision_engine=DecisionEngine(intent_router=ScanAwareIntentRouter()),
        context_manager=context_manager,
        memory_service=memory,
    )


def timed_call(fn: Callable[[], T]) -> tuple[T, float]:
    started = time.perf_counter()
    result = fn()
    latency_ms = (time.perf_counter() - started) * 1000.0
    return result, latency_ms


async def timed_call_async(fn) -> tuple[Any, float]:
    started = time.perf_counter()
    result = await fn()
    latency_ms = (time.perf_counter() - started) * 1000.0
    return result, latency_ms


def dump(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model


def map_engine_error(exc: Exception) -> HTTPException:
    name = type(exc).__name__
    message = str(exc)
    details = getattr(exc, "details", None)
    if name in {
        "ScanValidationError",
        "ScanTargetParseError",
        "ScanAdapterError",
        "ScanIngestError",
    }:
        return HTTPException(
            status_code=400,
            detail={"code": name, "message": message, "details": details},
        )
    if name.endswith("NotFoundError"):
        return HTTPException(
            status_code=404,
            detail={"code": name, "message": message, "details": details},
        )
    if name in {"AccessDeniedError", "TenantIsolationError"}:
        return HTTPException(
            status_code=403,
            detail={"code": name, "message": message, "details": details},
        )
    if name in {
        "InvalidScoringInputError",
        "InvalidRiskInputError",
        "InvalidDecisionRequestError",
        "InvalidPlanRequestError",
        "InvalidSimulationRequestError",
        "InvalidApprovalRequestError",
        "InvalidExecutionRequestError",
        "InvalidVerificationRequestError",
        "InvalidReportingRequestError",
        "UnsupportedDecisionForPlanningError",
        "ApprovalStateError",
        "ExecutionStateError",
        "VerificationStateError",
        "ExportError",
    }:
        return HTTPException(
            status_code=400,
            detail={"code": name, "message": message, "details": details},
        )
    return HTTPException(
        status_code=500,
        detail={"code": name or "INTERNAL_ERROR", "message": message, "details": details},
    )
