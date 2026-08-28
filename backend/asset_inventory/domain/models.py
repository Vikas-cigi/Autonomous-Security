"""Core Asset Inventory domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from asset_inventory.domain.classification import AssetClassification
from asset_inventory.domain.enums import (
    AssetStatus,
    AssetType,
    CloudProvider,
    EnvironmentKind,
    RelationshipType,
)
from asset_inventory.domain.metadata import CloudMetadata, KubernetesMetadata


class AssetOwner(FortiBaseModel):
    """Human or team owner accountable for an asset."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    display_name: str = Field(..., min_length=1, max_length=256)
    email: Optional[str] = Field(default=None, max_length=320)
    team: Optional[str] = Field(default=None, max_length=256)
    owner_type: str = Field(
        default="user",
        description="user | team | service | system",
    )
    external_id: Optional[str] = Field(
        default=None,
        max_length=256,
        description="IdP / CMDB owner reference.",
    )
    is_primary: bool = Field(default=True)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("email must be a valid address shape")
        return value.lower()

    @field_validator("owner_type")
    @classmethod
    def validate_owner_type(cls, value: str) -> str:
        allowed = {"user", "team", "service", "system"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"owner_type must be one of {sorted(allowed)}")
        return normalized


class BusinessUnit(TimestampedModel):
    """Organizational business unit for ownership and reporting."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    name: str = Field(..., min_length=1, max_length=256)
    code: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=2000)
    parent_id: Optional[UUID] = Field(
        default=None,
        description="Optional parent business unit for hierarchy.",
    )
    cost_center: Optional[str] = Field(default=None, max_length=64)
    is_active: bool = Field(default=True)


class Environment(TimestampedModel):
    """Named environment (prod, staging, etc.) scoped to a tenant."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    name: str = Field(..., min_length=1, max_length=128)
    kind: EnvironmentKind = Field(default=EnvironmentKind.OTHER)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_production: bool = Field(default=False)
    region_hint: Optional[str] = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def sync_production_flag(self) -> Environment:
        if self.kind == EnvironmentKind.PRODUCTION and not self.is_production:
            # Avoid validate_assignment recursion on self-mutation.
            object.__setattr__(self, "is_production", True)
        return self


class AssetRelationship(TimestampedModel):
    """Directed relationship between two assets within a tenant."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    source_asset_id: UUID = Field(...)
    target_asset_id: UUID = Field(...)
    relationship_type: RelationshipType = Field(...)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = Field(default=True)

    @model_validator(mode="after")
    def no_self_edge(self) -> AssetRelationship:
        if self.source_asset_id == self.target_asset_id:
            raise ValueError("source_asset_id and target_asset_id must differ")
        return self


class Asset(TimestampedModel):
    """
    Authoritative inventory record for a platform asset.

    ``SecurityFindingObject.asset_id`` must reference ``Asset.id``.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    name: str = Field(..., min_length=1, max_length=256)
    display_name: Optional[str] = Field(default=None, max_length=256)
    asset_type: AssetType = Field(...)
    status: AssetStatus = Field(default=AssetStatus.ACTIVE)
    description: Optional[str] = Field(default=None, max_length=4000)

    external_id: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Stable external identity (instance id, ARN, etc.).",
    )
    hostname: Optional[str] = Field(default=None, max_length=253)
    fqdn: Optional[str] = Field(default=None, max_length=253)

    business_unit_id: Optional[UUID] = None
    environment_id: Optional[UUID] = None
    owners: List[AssetOwner] = Field(default_factory=list)

    classification: AssetClassification = Field(default_factory=AssetClassification)
    criticality_score: float = Field(default=0.5, ge=0.0, le=1.0)

    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Platform inventory tags (key/value).",
    )
    compliance_tags: List[str] = Field(
        default_factory=list,
        description="Denormalized compliance tags for search.",
    )

    cloud: CloudMetadata = Field(default_factory=CloudMetadata)
    kubernetes: Optional[KubernetesMetadata] = None

    current_version: int = Field(default=1, ge=1)
    discovered_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None

    @field_validator("tags")
    @classmethod
    def limit_tags(cls, value: Dict[str, str]) -> Dict[str, str]:
        if len(value) > 64:
            raise ValueError("tags limited to 64 entries")
        for key, item in value.items():
            if len(key) > 128 or len(item) > 512:
                raise ValueError("tag key/value lengths exceed limits")
        return value

    @field_validator("compliance_tags")
    @classmethod
    def normalize_compliance(cls, value: List[str]) -> List[str]:
        return [t.strip().lower() for t in value if t.strip()][:32]

    @field_validator("discovered_at", "last_seen_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def sync_compliance_and_cloud(self) -> Asset:
        # Keep top-level compliance_tags aligned with classification.
        if self.classification.compliance_tags and not self.compliance_tags:
            object.__setattr__(
                self,
                "compliance_tags",
                list(self.classification.compliance_tags),
            )
        elif self.compliance_tags and not self.classification.compliance_tags:
            object.__setattr__(
                self.classification,
                "compliance_tags",
                list(self.compliance_tags),
            )

        # Infer cloud provider from asset type when unset.
        if self.cloud.provider == CloudProvider.NONE:
            inferred = {
                AssetType.EC2: CloudProvider.AWS,
                AssetType.LAMBDA: CloudProvider.AWS,
                AssetType.S3: CloudProvider.AWS,
                AssetType.RDS: CloudProvider.AWS,
                AssetType.API_GATEWAY: CloudProvider.AWS,
                AssetType.AZURE_VM: CloudProvider.AZURE,
                AssetType.GCP_VM: CloudProvider.GCP,
            }.get(self.asset_type)
            if inferred:
                object.__setattr__(self.cloud, "provider", inferred)
        return self

    def primary_owner(self) -> Optional[AssetOwner]:
        """Return the primary owner if present."""

        for owner in self.owners:
            if owner.is_primary:
                return owner
        return self.owners[0] if self.owners else None

    def touch_seen(self) -> None:
        """Mark asset as observed now."""

        self.last_seen_at = utc_now()
        self.touch()
