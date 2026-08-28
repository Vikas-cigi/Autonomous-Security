"""Map between domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from asset_inventory.domain.enums import AssetStatus, AuditAction
from asset_inventory.domain.history import AssetHistory, AssetVersion
from asset_inventory.domain.models import (
    Asset,
    AssetRelationship,
    BusinessUnit,
    Environment,
)
from asset_inventory.persistence.orm import (
    AssetHistoryORM,
    AssetORM,
    AssetRelationshipORM,
    AssetVersionORM,
    BusinessUnitORM,
    EnvironmentORM,
)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def asset_to_orm(asset: Asset, *, current_version: int) -> AssetORM:
    payload = asset.model_dump(mode="json")
    return AssetORM(
        id=asset.id,
        tenant_id=asset.tenant_id,
        name=asset.name,
        display_name=asset.display_name,
        asset_type=asset.asset_type.value,
        status=asset.status.value,
        external_id=asset.external_id,
        hostname=asset.hostname,
        fqdn=asset.fqdn,
        business_unit_id=asset.business_unit_id,
        environment_id=asset.environment_id,
        criticality_score=asset.criticality_score,
        criticality_tier=asset.classification.criticality_tier.value,
        exposure_level=asset.classification.internet_exposure.level.value,
        cloud_provider=asset.cloud.provider.value,
        crown_jewel=asset.classification.crown_jewel,
        current_version=current_version,
        payload=payload,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def apply_asset_to_orm(row: AssetORM, asset: Asset, *, current_version: int) -> None:
    row.name = asset.name
    row.display_name = asset.display_name
    row.asset_type = asset.asset_type.value
    row.status = asset.status.value
    row.external_id = asset.external_id
    row.hostname = asset.hostname
    row.fqdn = asset.fqdn
    row.business_unit_id = asset.business_unit_id
    row.environment_id = asset.environment_id
    row.criticality_score = asset.criticality_score
    row.criticality_tier = asset.classification.criticality_tier.value
    row.exposure_level = asset.classification.internet_exposure.level.value
    row.cloud_provider = asset.cloud.provider.value
    row.crown_jewel = asset.classification.crown_jewel
    row.current_version = current_version
    row.payload = asset.model_dump(mode="json")
    row.updated_at = asset.updated_at


def orm_to_asset(row: AssetORM) -> Asset:
    return Asset.model_validate(row.payload)


def business_unit_to_orm(unit: BusinessUnit) -> BusinessUnitORM:
    return BusinessUnitORM(
        id=unit.id,
        tenant_id=unit.tenant_id,
        name=unit.name,
        code=unit.code,
        description=unit.description,
        parent_id=unit.parent_id,
        cost_center=unit.cost_center,
        is_active=unit.is_active,
        payload=unit.model_dump(mode="json"),
        created_at=unit.created_at,
        updated_at=unit.updated_at,
    )


def apply_business_unit_to_orm(row: BusinessUnitORM, unit: BusinessUnit) -> None:
    row.name = unit.name
    row.code = unit.code
    row.description = unit.description
    row.parent_id = unit.parent_id
    row.cost_center = unit.cost_center
    row.is_active = unit.is_active
    row.payload = unit.model_dump(mode="json")
    row.updated_at = unit.updated_at


def orm_to_business_unit(row: BusinessUnitORM) -> BusinessUnit:
    return BusinessUnit.model_validate(row.payload)


def environment_to_orm(env: Environment) -> EnvironmentORM:
    return EnvironmentORM(
        id=env.id,
        tenant_id=env.tenant_id,
        name=env.name,
        kind=env.kind.value,
        description=env.description,
        is_production=env.is_production,
        region_hint=env.region_hint,
        payload=env.model_dump(mode="json"),
        created_at=env.created_at,
        updated_at=env.updated_at,
    )


def apply_environment_to_orm(row: EnvironmentORM, env: Environment) -> None:
    row.name = env.name
    row.kind = env.kind.value
    row.description = env.description
    row.is_production = env.is_production
    row.region_hint = env.region_hint
    row.payload = env.model_dump(mode="json")
    row.updated_at = env.updated_at


def orm_to_environment(row: EnvironmentORM) -> Environment:
    return Environment.model_validate(row.payload)


def relationship_to_orm(rel: AssetRelationship) -> AssetRelationshipORM:
    return AssetRelationshipORM(
        id=rel.id,
        tenant_id=rel.tenant_id,
        source_asset_id=rel.source_asset_id,
        target_asset_id=rel.target_asset_id,
        relationship_type=rel.relationship_type.value,
        description=rel.description,
        is_active=rel.is_active,
        payload=rel.model_dump(mode="json"),
        created_at=rel.created_at,
        updated_at=rel.updated_at,
    )


def apply_relationship_to_orm(
    row: AssetRelationshipORM,
    rel: AssetRelationship,
) -> None:
    row.source_asset_id = rel.source_asset_id
    row.target_asset_id = rel.target_asset_id
    row.relationship_type = rel.relationship_type.value
    row.description = rel.description
    row.is_active = rel.is_active
    row.payload = rel.model_dump(mode="json")
    row.updated_at = rel.updated_at


def orm_to_relationship(row: AssetRelationshipORM) -> AssetRelationship:
    return AssetRelationship.model_validate(row.payload)


def asset_version_from_orm(row: AssetVersionORM) -> AssetVersion:
    return AssetVersion(
        id=row.id,
        asset_id=row.asset_id,
        tenant_id=row.tenant_id,
        version=row.version,
        snapshot=Asset.model_validate(row.payload),
        change_summary=row.change_summary,
        created_by=row.created_by,
        created_at=_as_utc(row.created_at),
    )


def history_from_orm(row: AssetHistoryORM) -> AssetHistory:
    return AssetHistory(
        id=row.id,
        asset_id=row.asset_id,
        tenant_id=row.tenant_id,
        action=AuditAction(row.action),
        from_status=AssetStatus(row.from_status) if row.from_status else None,
        to_status=AssetStatus(row.to_status) if row.to_status else None,
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        created_at=_as_utc(row.created_at),
    )
