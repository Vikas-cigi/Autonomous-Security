"""Asset Inventory exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class AssetInventoryError(Exception):
    """Base error for the Asset Inventory."""

    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class AssetNotFoundError(AssetInventoryError):
    """Raised when an asset cannot be located for the tenant."""

    def __init__(self, asset_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Asset {asset_id} not found for tenant {tenant_id}",
            details={"asset_id": str(asset_id), "tenant_id": str(tenant_id)},
        )
        self.asset_id = asset_id
        self.tenant_id = tenant_id


class BusinessUnitNotFoundError(AssetInventoryError):
    def __init__(self, business_unit_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Business unit {business_unit_id} not found for tenant {tenant_id}",
            details={
                "business_unit_id": str(business_unit_id),
                "tenant_id": str(tenant_id),
            },
        )


class EnvironmentNotFoundError(AssetInventoryError):
    def __init__(self, environment_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Environment {environment_id} not found for tenant {tenant_id}",
            details={
                "environment_id": str(environment_id),
                "tenant_id": str(tenant_id),
            },
        )


class RelationshipNotFoundError(AssetInventoryError):
    def __init__(self, relationship_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Relationship {relationship_id} not found for tenant {tenant_id}",
            details={
                "relationship_id": str(relationship_id),
                "tenant_id": str(tenant_id),
            },
        )


class TenantIsolationError(AssetInventoryError):
    """Raised when a cross-tenant access attempt is detected."""


class DuplicateExternalIdError(AssetInventoryError):
    """Raised when external_id collides within a tenant."""
