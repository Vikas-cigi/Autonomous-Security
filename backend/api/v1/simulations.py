"""Simulation Engine HTTP API."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

from api.deps import dump, get_simulation_container, map_engine_error, timed_call
from simulation_engine.domain.inputs import SimulationRequest
from simulation_engine.query.filters import SimulationSearchFilter
from simulation_engine.query.pagination import PageRequest
from utils.response import error_response, success_response

router = APIRouter(prefix="/simulations", tags=["Simulation Engine"])


@router.post("")
def simulate(body: SimulationRequest):
    try:
        container = get_simulation_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(lambda: svc.engine.simulate(body))
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Simulation completed",
            )
    except Exception as exc:
        http_exc = map_engine_error(exc)
        if http_exc.status_code < 500:
            return error_response(
                code=http_exc.detail["code"],
                details=http_exc.detail.get("details") or http_exc.detail["message"],
                message=http_exc.detail["message"],
            )
        raise http_exc from exc


@router.get("")
def search_simulations(
    tenant_id: UUID = Query(...),
    plan_id: Optional[UUID] = Query(None),
    finding_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    try:
        container = get_simulation_container()
        with container.session() as session:
            svc = container.build(session)
            filters = SimulationSearchFilter(
                tenant_id=tenant_id,
                plan_id=plan_id,
                finding_id=finding_id,
            )
            result, latency = timed_call(
                lambda: svc.engine.search(
                    filters, PageRequest(page=page, page_size=page_size)
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Simulations search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/by-plan/{plan_id}")
def get_simulation_for_plan(plan_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_simulation_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.find_by_plan(plan_id, tenant_id)
            )
            return success_response(
                data=dump(result) if result else None,
                latency_ms=latency,
                message="Simulation for plan",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/{simulation_id}")
def get_simulation(simulation_id: UUID, tenant_id: UUID = Query(...)):
    try:
        container = get_simulation_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.engine.get(simulation_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Simulation retrieved",
            )
    except Exception as exc:
        http_exc = map_engine_error(exc)
        if http_exc.status_code == 404:
            return error_response(
                code=http_exc.detail["code"],
                details=http_exc.detail.get("details"),
                message=http_exc.detail["message"],
            )
        raise http_exc from exc
