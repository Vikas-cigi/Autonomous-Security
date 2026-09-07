"""Asset Inventory HTTP API — query persisted assets."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query

from api.deps import dump, get_asset_container, map_engine_error, timed_call
from asset_inventory.domain.enums import AssetStatus, AssetType
from asset_inventory.query.filters import AssetSearchFilter
from asset_inventory.query.pagination import PageRequest
from utils.response import error_response, success_response

router = APIRouter(prefix="/assets", tags=["Asset Inventory"])


@router.get("")
def search_assets(
    tenant_id: UUID = Query(...),
    asset_type: List[AssetType] = Query(default=[]),
    status: List[AssetStatus] = Query(default=[]),
    text: Optional[str] = Query(None, max_length=256),
    internet_facing_only: bool = Query(default=False),
    crown_jewel_only: bool = Query(default=False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Paginated asset search. ``tenant_id`` is required for isolation."""

    try:
        container = get_asset_container()
        with container.session() as session:
            svc = container.build(session)
            filters = AssetSearchFilter(
                tenant_id=tenant_id,
                asset_types=asset_type or None,
                statuses=status or None,
                text=text,
                internet_facing_only=internet_facing_only,
                crown_jewel_only=crown_jewel_only,
            )
            result, latency = timed_call(
                lambda: svc.assets.search(
                    filters, PageRequest(page=page, page_size=page_size)
                )
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Assets search",
            )
    except Exception as exc:
        raise map_engine_error(exc) from exc


@router.get("/{asset_id}")
def get_asset(
    asset_id: UUID,
    tenant_id: UUID = Query(...),
):
    """Return one asset scoped to ``tenant_id``."""

    try:
        container = get_asset_container()
        with container.session() as session:
            svc = container.build(session)
            result, latency = timed_call(
                lambda: svc.assets.get(asset_id, tenant_id)
            )
            return success_response(
                data=dump(result),
                latency_ms=latency,
                message="Asset retrieved",
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
