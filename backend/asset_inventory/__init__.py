"""
Enterprise Asset Inventory — authoritative catalog of platform assets.

``SecurityFindingObject.asset_id`` must reference an ``Asset.id`` from this
service. Does not modify Decision Engine, Context Manager, Prompt Builder,
Provider Factory, Normalization, Policy Engine, Adapters, or Evidence Repository.
"""

from asset_inventory.di.container import AssetInventoryContainer
from asset_inventory.domain.classification import AssetClassification, InternetExposure
from asset_inventory.domain.history import AssetHistory, AssetVersion
from asset_inventory.domain.models import (
    Asset,
    AssetOwner,
    AssetRelationship,
    BusinessUnit,
    Environment,
)
from asset_inventory.domain.scoring import CriticalityScore, CriticalityScorer
from asset_inventory.interfaces.repository import AssetRepository
from asset_inventory.persistence.postgres_repository import PostgresAssetRepository
from asset_inventory.query.filters import AssetSearchFilter
from asset_inventory.query.pagination import Page, PageRequest
from asset_inventory.services.asset_service import AssetService

__all__ = [
    "Asset",
    "AssetClassification",
    "AssetHistory",
    "AssetInventoryContainer",
    "AssetOwner",
    "AssetRelationship",
    "AssetRepository",
    "AssetSearchFilter",
    "AssetService",
    "AssetVersion",
    "BusinessUnit",
    "CriticalityScore",
    "CriticalityScorer",
    "Environment",
    "InternetExposure",
    "Page",
    "PageRequest",
    "PostgresAssetRepository",
]

__version__ = "1.0.0"
