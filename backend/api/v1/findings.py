"""Evidence Repository HTTP API — query persisted findings."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query

from api.deps import dump, get_evidence_container, map_engine_error, timed_call
from evidence_repository.domain.enums import LifecycleState
from evidence_repository.query.filters import FindingSearchFilter
from evidence_repository.query.pagination import PageRequest
from models.enums import FindingStatus, FindingType, Severity, SourceTool
from utils.response import error_response, success_response

router = APIRouter(prefix="/findings", tags=["Evidence / Findings"])


@router.get("")
def search_findings(
    tenant_id: UUID = Query(...),
    asset_id: Optional[UUID] = Query(None),
    severity: List[Severity] = Query(default=[]),
    status: List[FindingStatus] = Query(default=[]),
    scanner: List[SourceTool] = Query(default=[]),
    finding_type: List[FindingType] = Query(default=[]),
    lifecycle: List[LifecycleState] = Query(default=[]),
    cve_id: Optional[str] = Query(None),
    text: Optional[str] = Query(None, max_length=512),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Paginated finding search. ``tenant_id`` is required for isolation."""

    try:
        container = get_evidence_container()
        with container.session() as session:
            svc = container.build(session)
            filters = FindingSearchFilter(
                tenant_id=tenant_id,
                asset_id=asset_id,
                severities=severity,
                statuses=status,
                scanners=scanner,
                finding_types=finding_type,
                lifecycles=lifecycle,
                cve_id=cve_id,
                text=text,
            )
            result, latency = timed_call(
                lambda: svc.search.search(
                    filters, PageRequest(page=page, page_size=page_size)
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Findings search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/{finding_id}")
def get_finding(
    finding_id: UUID,
    tenant_id: UUID = Query(...),
):
    """Return one finding (including evidence) scoped to ``tenant_id``."""

    try:
        container = get_evidence_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.repository.get_finding(finding_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Finding retrieved",
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


@router.get("/{finding_id}/history")
def get_finding_history(
    finding_id: UUID,
    tenant_id: UUID = Query(...),
):
    """Append-only finding history for the tenant."""

    try:
        container = get_evidence_container()
        with container.session() as session:
            svc = container.build(session)
            # Confirm the finding exists (and is tenant-scoped) before listing history.
            svc.repository.get_finding(finding_id, tenant_id)
            result, latency = timed_call(
                lambda: svc.repository.list_finding_history(finding_id, tenant_id)
            )
            return success_response(
                data=[dump(item) for item in result],
                latency_ms=latency,
                message="Finding history",
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
