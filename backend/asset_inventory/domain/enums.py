"""Domain enums for the Asset Inventory."""

from __future__ import annotations

from enum import Enum


class AssetType(str, Enum):
    """Supported asset classes across cloud and container platforms."""

    EC2 = "ec2"
    AZURE_VM = "azure_vm"
    GCP_VM = "gcp_vm"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    LAMBDA = "lambda"
    S3 = "s3"
    RDS = "rds"
    API_GATEWAY = "api_gateway"
    OTHER = "other"


class CloudProvider(str, Enum):
    """Cloud provider for cloud-hosted assets."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    OTHER = "other"
    NONE = "none"


class AssetStatus(str, Enum):
    """Lifecycle status of an inventory asset."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DECOMMISSIONED = "decommissioned"
    UNKNOWN = "unknown"


class EnvironmentKind(str, Enum):
    """Logical deployment environment classification."""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"
    SANDBOX = "sandbox"
    DR = "disaster_recovery"
    OTHER = "other"


class RelationshipType(str, Enum):
    """Directed relationship between two assets."""

    DEPENDS_ON = "depends_on"
    HOSTS = "hosts"
    CONTAINS = "contains"
    CONNECTS_TO = "connects_to"
    PROTECTS = "protects"
    OWNED_BY_GROUP = "owned_by_group"
    RELATED = "related"


class CriticalityTier(str, Enum):
    """Business / security criticality tier derived from scoring."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ExposureLevel(str, Enum):
    """Internet / network exposure classification."""

    PUBLIC_INTERNET = "public_internet"
    PARTNER = "partner"
    CORPORATE = "corporate"
    PRIVATE = "private"
    ISOLATED = "isolated"
    UNKNOWN = "unknown"


class DataSensitivity(str, Enum):
    """Data sensitivity classification for the asset."""

    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
    INTERNAL = "internal"
    PUBLIC = "public"
    UNKNOWN = "unknown"


class AuditAction(str, Enum):
    """Audit actions for the Asset Inventory."""

    ASSET_CREATED = "asset_created"
    ASSET_UPDATED = "asset_updated"
    ASSET_DECOMMISSIONED = "asset_decommissioned"
    ASSET_TAGGED = "asset_tagged"
    OWNER_ASSIGNED = "owner_assigned"
    RELATIONSHIP_ADDED = "relationship_added"
    RELATIONSHIP_REMOVED = "relationship_removed"
    BUSINESS_UNIT_UPSERTED = "business_unit_upserted"
    ENVIRONMENT_UPSERTED = "environment_upserted"
    SEARCHED = "searched"
    SCORE_RECOMPUTED = "score_recomputed"
