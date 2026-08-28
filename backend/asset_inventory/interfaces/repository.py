"""AssetRepository port (hexagonal interface)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from asset_inventory.domain.history import AssetHistory, AssetVersion
from asset_inventory.domain.models import (
    Asset,
    AssetOwner,
    AssetRelationship,
    BusinessUnit,
    Environment,
)
from asset_inventory.query.filters import AssetSearchFilter
from asset_inventory.query.pagination import Page, PageRequest


class AssetRepository(ABC):
    """
    Persistence port for the enterprise asset catalog.

    All methods that accept ``tenant_id`` enforce multi-tenant isolation.
    """

    # ---- Assets -----------------------------------------------------------

    @abstractmethod
    def save_asset(
        self,
        asset: Asset,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Asset persisted",
    ) -> Asset:
        """Insert or update an asset; creates a version + history entry."""

    @abstractmethod
    def get_asset(self, asset_id: UUID, tenant_id: UUID) -> Asset:
        """Fetch an asset by id scoped to tenant."""

    @abstractmethod
    def find_by_external_id(
        self,
        tenant_id: UUID,
        external_id: str,
    ) -> Optional[Asset]:
        """Lookup by stable external identity within a tenant."""

    @abstractmethod
    def delete_asset(
        self,
        asset_id: UUID,
        tenant_id: UUID,
        *,
        actor: Optional[str] = None,
        soft: bool = True,
    ) -> Asset:
        """Soft-decommission (default) or hard-delete an asset."""

    @abstractmethod
    def list_asset_versions(
        self,
        asset_id: UUID,
        tenant_id: UUID,
    ) -> List[AssetVersion]:
        """Return immutable versions ordered by version asc."""

    @abstractmethod
    def list_asset_history(
        self,
        asset_id: UUID,
        tenant_id: UUID,
    ) -> List[AssetHistory]:
        """Return append-only history ordered by time asc."""

    @abstractmethod
    def search_assets(
        self,
        filters: AssetSearchFilter,
        page: PageRequest,
    ) -> Page[Asset]:
        """Paginated filtered search with mandatory tenant scope."""

    # ---- Owners -----------------------------------------------------------

    @abstractmethod
    def set_owners(
        self,
        asset_id: UUID,
        tenant_id: UUID,
        owners: List[AssetOwner],
        *,
        actor: Optional[str] = None,
    ) -> Asset:
        """Replace owners for an asset."""

    # ---- Organizational ---------------------------------------------------

    @abstractmethod
    def save_business_unit(
        self,
        unit: BusinessUnit,
        *,
        actor: Optional[str] = None,
    ) -> BusinessUnit:
        """Upsert a business unit."""

    @abstractmethod
    def get_business_unit(
        self,
        business_unit_id: UUID,
        tenant_id: UUID,
    ) -> BusinessUnit:
        """Fetch business unit by id."""

    @abstractmethod
    def list_business_units(self, tenant_id: UUID) -> List[BusinessUnit]:
        """List business units for a tenant."""

    @abstractmethod
    def save_environment(
        self,
        environment: Environment,
        *,
        actor: Optional[str] = None,
    ) -> Environment:
        """Upsert an environment."""

    @abstractmethod
    def get_environment(
        self,
        environment_id: UUID,
        tenant_id: UUID,
    ) -> Environment:
        """Fetch environment by id."""

    @abstractmethod
    def list_environments(self, tenant_id: UUID) -> List[Environment]:
        """List environments for a tenant."""

    # ---- Relationships ----------------------------------------------------

    @abstractmethod
    def save_relationship(
        self,
        relationship: AssetRelationship,
        *,
        actor: Optional[str] = None,
    ) -> AssetRelationship:
        """Create or update a relationship edge."""

    @abstractmethod
    def list_relationships(
        self,
        tenant_id: UUID,
        *,
        asset_id: Optional[UUID] = None,
    ) -> List[AssetRelationship]:
        """List relationships, optionally filtered to an asset endpoint."""

    @abstractmethod
    def remove_relationship(
        self,
        relationship_id: UUID,
        tenant_id: UUID,
        *,
        actor: Optional[str] = None,
    ) -> None:
        """Deactivate / remove a relationship."""
