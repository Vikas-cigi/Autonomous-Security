"""Search / filter models for Asset Inventory."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from asset_inventory.domain.enums import (
    AssetStatus,
    AssetType,
    CloudProvider,
    CriticalityTier,
    EnvironmentKind,
    ExposureLevel,
)


class AssetSearchFilter(FortiBaseModel):
    """Mandatory tenant-scoped filter for asset search."""

    tenant_id: UUID = Field(..., description="Required tenant isolation key.")
    asset_types: Optional[List[AssetType]] = None
    statuses: Optional[List[AssetStatus]] = None
    business_unit_id: Optional[UUID] = None
    environment_id: Optional[UUID] = None
    environment_kinds: Optional[List[EnvironmentKind]] = None
    cloud_providers: Optional[List[CloudProvider]] = None
    criticality_tiers: Optional[List[CriticalityTier]] = None
    exposure_levels: Optional[List[ExposureLevel]] = None
    compliance_tags: Optional[List[str]] = None
    tags: Optional[dict[str, str]] = None
    text: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Case-insensitive match on name / hostname / external_id.",
    )
    internet_facing_only: bool = Field(default=False)
    crown_jewel_only: bool = Field(default=False)
