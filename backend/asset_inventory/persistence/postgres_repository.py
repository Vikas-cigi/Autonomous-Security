"""
PostgreSQL-compatible AssetRepository implementation (SQLAlchemy 2.x).
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.orm import Session

from models.common import utc_now
from asset_inventory.domain.enums import AssetStatus, AuditAction, ExposureLevel
from asset_inventory.domain.history import AssetHistory, AssetVersion
from asset_inventory.domain.models import (
    Asset,
    AssetOwner,
    AssetRelationship,
    BusinessUnit,
    Environment,
)
from asset_inventory.exceptions import (
    AssetNotFoundError,
    BusinessUnitNotFoundError,
    DuplicateExternalIdError,
    EnvironmentNotFoundError,
    RelationshipNotFoundError,
)
from asset_inventory.interfaces.repository import AssetRepository
from asset_inventory.persistence.mappers import (
    apply_asset_to_orm,
    apply_business_unit_to_orm,
    apply_environment_to_orm,
    apply_relationship_to_orm,
    asset_to_orm,
    asset_version_from_orm,
    business_unit_to_orm,
    environment_to_orm,
    history_from_orm,
    orm_to_asset,
    orm_to_business_unit,
    orm_to_environment,
    orm_to_relationship,
    relationship_to_orm,
)
from asset_inventory.persistence.orm import (
    AssetHistoryORM,
    AssetORM,
    AssetRelationshipORM,
    AssetVersionORM,
    BusinessUnitORM,
    EnvironmentORM,
)
from asset_inventory.query.filters import AssetSearchFilter
from asset_inventory.query.pagination import Page, PageRequest
from asset_inventory.services.audit import AuditLogger

logger = logging.getLogger(__name__)


class PostgresAssetRepository(AssetRepository):
    """SQLAlchemy-backed repository (PostgreSQL production, SQLite tests)."""

    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def save_asset(
        self,
        asset: Asset,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Asset persisted",
    ) -> Asset:
        if asset.external_id:
            self._assert_external_id_unique(asset)

        row = self._session.get(AssetORM, asset.id)
        created = row is None
        from_status: Optional[AssetStatus] = None
        if created:
            version = 1
            asset.current_version = version
            asset.touch()
            row = asset_to_orm(asset, current_version=version)
            self._session.add(row)
            action = AuditAction.ASSET_CREATED
        else:
            if row.tenant_id != asset.tenant_id:
                raise AssetNotFoundError(asset.id, asset.tenant_id)
            from_status = AssetStatus(row.status)
            version = int(row.current_version) + 1
            asset.current_version = version
            asset.touch()
            apply_asset_to_orm(row, asset, current_version=version)
            action = AuditAction.ASSET_UPDATED

        self._session.flush()
        self._add_version(asset, version=version, actor=actor, summary=change_summary)
        self._add_history(
            asset_id=asset.id,
            tenant_id=asset.tenant_id,
            action=action,
            from_status=from_status,
            to_status=asset.status,
            actor=actor,
            message=change_summary,
        )
        self._audit.log(
            tenant_id=asset.tenant_id,
            action=action,
            message=change_summary,
            actor=actor,
            details={"asset_id": str(asset.id), "version": version},
        )
        self._session.flush()
        return orm_to_asset(row)

    def get_asset(self, asset_id: UUID, tenant_id: UUID) -> Asset:
        row = self._require_asset(asset_id, tenant_id)
        return orm_to_asset(row)

    def find_by_external_id(
        self,
        tenant_id: UUID,
        external_id: str,
    ) -> Optional[Asset]:
        stmt = select(AssetORM).where(
            AssetORM.tenant_id == tenant_id,
            AssetORM.external_id == external_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_asset(row) if row else None

    def delete_asset(
        self,
        asset_id: UUID,
        tenant_id: UUID,
        *,
        actor: Optional[str] = None,
        soft: bool = True,
    ) -> Asset:
        row = self._require_asset(asset_id, tenant_id)
        asset = orm_to_asset(row)
        if soft:
            from_status = asset.status
            asset.status = AssetStatus.DECOMMISSIONED
            asset.touch()
            return self.save_asset(
                asset,
                actor=actor,
                change_summary="Asset decommissioned",
            )
        self._session.delete(row)
        self._audit.log(
            tenant_id=tenant_id,
            action=AuditAction.ASSET_DECOMMISSIONED,
            message="Asset hard-deleted",
            actor=actor,
            details={"asset_id": str(asset_id)},
        )
        self._session.flush()
        return asset

    def list_asset_versions(
        self,
        asset_id: UUID,
        tenant_id: UUID,
    ) -> List[AssetVersion]:
        self._require_asset(asset_id, tenant_id)
        stmt = (
            select(AssetVersionORM)
            .where(
                AssetVersionORM.asset_id == asset_id,
                AssetVersionORM.tenant_id == tenant_id,
            )
            .order_by(AssetVersionORM.version.asc())
        )
        return [asset_version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def list_asset_history(
        self,
        asset_id: UUID,
        tenant_id: UUID,
    ) -> List[AssetHistory]:
        self._require_asset(asset_id, tenant_id)
        stmt = (
            select(AssetHistoryORM)
            .where(
                AssetHistoryORM.asset_id == asset_id,
                AssetHistoryORM.tenant_id == tenant_id,
            )
            .order_by(AssetHistoryORM.created_at.asc())
        )
        return [history_from_orm(r) for r in self._session.scalars(stmt).all()]

    def search_assets(
        self,
        filters: AssetSearchFilter,
        page: PageRequest,
    ) -> Page[Asset]:
        stmt = select(AssetORM).where(AssetORM.tenant_id == filters.tenant_id)
        stmt = self._apply_filters(stmt, filters)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(AssetORM.criticality_score.desc(), AssetORM.name.asc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_asset(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Asset search",
            details={"total": total, "page": page.page},
        )
        return Page.from_items(items, request=page, total_items=total)

    def set_owners(
        self,
        asset_id: UUID,
        tenant_id: UUID,
        owners: List[AssetOwner],
        *,
        actor: Optional[str] = None,
    ) -> Asset:
        asset = self.get_asset(asset_id, tenant_id)
        for owner in owners:
            if owner.tenant_id != tenant_id:
                raise AssetNotFoundError(asset_id, tenant_id)
        asset.owners = owners
        asset.touch()
        saved = self.save_asset(
            asset,
            actor=actor,
            change_summary="Owners assigned",
        )
        self._audit.log(
            tenant_id=tenant_id,
            action=AuditAction.OWNER_ASSIGNED,
            message="Owners replaced",
            actor=actor,
            details={"asset_id": str(asset_id), "owner_count": len(owners)},
        )
        return saved

    # ------------------------------------------------------------------
    # Organizational
    # ------------------------------------------------------------------

    def save_business_unit(
        self,
        unit: BusinessUnit,
        *,
        actor: Optional[str] = None,
    ) -> BusinessUnit:
        row = self._session.get(BusinessUnitORM, unit.id)
        if row is None:
            unit.touch()
            row = business_unit_to_orm(unit)
            self._session.add(row)
        else:
            if row.tenant_id != unit.tenant_id:
                raise BusinessUnitNotFoundError(unit.id, unit.tenant_id)
            unit.touch()
            apply_business_unit_to_orm(row, unit)
        self._audit.log(
            tenant_id=unit.tenant_id,
            action=AuditAction.BUSINESS_UNIT_UPSERTED,
            message=f"Business unit upserted: {unit.name}",
            actor=actor,
            details={"business_unit_id": str(unit.id)},
        )
        self._session.flush()
        return orm_to_business_unit(row)

    def get_business_unit(
        self,
        business_unit_id: UUID,
        tenant_id: UUID,
    ) -> BusinessUnit:
        row = self._session.get(BusinessUnitORM, business_unit_id)
        if row is None or row.tenant_id != tenant_id:
            raise BusinessUnitNotFoundError(business_unit_id, tenant_id)
        return orm_to_business_unit(row)

    def list_business_units(self, tenant_id: UUID) -> List[BusinessUnit]:
        stmt = (
            select(BusinessUnitORM)
            .where(BusinessUnitORM.tenant_id == tenant_id)
            .order_by(BusinessUnitORM.name.asc())
        )
        return [orm_to_business_unit(r) for r in self._session.scalars(stmt).all()]

    def save_environment(
        self,
        environment: Environment,
        *,
        actor: Optional[str] = None,
    ) -> Environment:
        row = self._session.get(EnvironmentORM, environment.id)
        if row is None:
            environment.touch()
            row = environment_to_orm(environment)
            self._session.add(row)
        else:
            if row.tenant_id != environment.tenant_id:
                raise EnvironmentNotFoundError(environment.id, environment.tenant_id)
            environment.touch()
            apply_environment_to_orm(row, environment)
        self._audit.log(
            tenant_id=environment.tenant_id,
            action=AuditAction.ENVIRONMENT_UPSERTED,
            message=f"Environment upserted: {environment.name}",
            actor=actor,
            details={"environment_id": str(environment.id)},
        )
        self._session.flush()
        return orm_to_environment(row)

    def get_environment(
        self,
        environment_id: UUID,
        tenant_id: UUID,
    ) -> Environment:
        row = self._session.get(EnvironmentORM, environment_id)
        if row is None or row.tenant_id != tenant_id:
            raise EnvironmentNotFoundError(environment_id, tenant_id)
        return orm_to_environment(row)

    def list_environments(self, tenant_id: UUID) -> List[Environment]:
        stmt = (
            select(EnvironmentORM)
            .where(EnvironmentORM.tenant_id == tenant_id)
            .order_by(EnvironmentORM.name.asc())
        )
        return [orm_to_environment(r) for r in self._session.scalars(stmt).all()]

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def save_relationship(
        self,
        relationship: AssetRelationship,
        *,
        actor: Optional[str] = None,
    ) -> AssetRelationship:
        self._require_asset(relationship.source_asset_id, relationship.tenant_id)
        self._require_asset(relationship.target_asset_id, relationship.tenant_id)
        row = self._session.get(AssetRelationshipORM, relationship.id)
        if row is None:
            relationship.touch()
            row = relationship_to_orm(relationship)
            self._session.add(row)
        else:
            if row.tenant_id != relationship.tenant_id:
                raise RelationshipNotFoundError(relationship.id, relationship.tenant_id)
            relationship.touch()
            apply_relationship_to_orm(row, relationship)
        self._add_history(
            asset_id=relationship.source_asset_id,
            tenant_id=relationship.tenant_id,
            action=AuditAction.RELATIONSHIP_ADDED,
            from_status=None,
            to_status=None,
            actor=actor,
            message=f"Relationship {relationship.relationship_type.value}",
            details={
                "relationship_id": str(relationship.id),
                "target_asset_id": str(relationship.target_asset_id),
            },
        )
        self._audit.log(
            tenant_id=relationship.tenant_id,
            action=AuditAction.RELATIONSHIP_ADDED,
            message="Relationship saved",
            actor=actor,
            details={"relationship_id": str(relationship.id)},
        )
        self._session.flush()
        return orm_to_relationship(row)

    def list_relationships(
        self,
        tenant_id: UUID,
        *,
        asset_id: Optional[UUID] = None,
    ) -> List[AssetRelationship]:
        stmt = select(AssetRelationshipORM).where(
            AssetRelationshipORM.tenant_id == tenant_id,
            AssetRelationshipORM.is_active.is_(True),
        )
        if asset_id is not None:
            stmt = stmt.where(
                or_(
                    AssetRelationshipORM.source_asset_id == asset_id,
                    AssetRelationshipORM.target_asset_id == asset_id,
                )
            )
        return [orm_to_relationship(r) for r in self._session.scalars(stmt).all()]

    def remove_relationship(
        self,
        relationship_id: UUID,
        tenant_id: UUID,
        *,
        actor: Optional[str] = None,
    ) -> None:
        row = self._session.get(AssetRelationshipORM, relationship_id)
        if row is None or row.tenant_id != tenant_id:
            raise RelationshipNotFoundError(relationship_id, tenant_id)
        row.is_active = False
        row.updated_at = utc_now()
        self._audit.log(
            tenant_id=tenant_id,
            action=AuditAction.RELATIONSHIP_REMOVED,
            message="Relationship deactivated",
            actor=actor,
            details={"relationship_id": str(relationship_id)},
        )
        self._session.flush()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_asset(self, asset_id: UUID, tenant_id: UUID) -> AssetORM:
        row = self._session.get(AssetORM, asset_id)
        if row is None or row.tenant_id != tenant_id:
            raise AssetNotFoundError(asset_id, tenant_id)
        return row

    def _assert_external_id_unique(self, asset: Asset) -> None:
        stmt = select(AssetORM).where(
            AssetORM.tenant_id == asset.tenant_id,
            AssetORM.external_id == asset.external_id,
            AssetORM.id != asset.id,
        )
        if self._session.scalars(stmt).first() is not None:
            raise DuplicateExternalIdError(
                f"external_id {asset.external_id!r} already exists for tenant",
                details={
                    "tenant_id": str(asset.tenant_id),
                    "external_id": asset.external_id,
                },
            )

    def _add_version(
        self,
        asset: Asset,
        *,
        version: int,
        actor: Optional[str],
        summary: str,
    ) -> None:
        self._session.add(
            AssetVersionORM(
                id=uuid4(),
                asset_id=asset.id,
                tenant_id=asset.tenant_id,
                version=version,
                change_summary=summary,
                created_by=actor,
                payload=asset.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )

    def _add_history(
        self,
        *,
        asset_id: UUID,
        tenant_id: UUID,
        action: AuditAction,
        from_status: Optional[AssetStatus],
        to_status: Optional[AssetStatus],
        actor: Optional[str],
        message: str,
        details: Optional[dict] = None,
    ) -> None:
        self._session.add(
            AssetHistoryORM(
                id=uuid4(),
                asset_id=asset_id,
                tenant_id=tenant_id,
                action=action.value,
                from_status=from_status.value if from_status else None,
                to_status=to_status.value if to_status else None,
                actor=actor,
                message=message,
                details=details or {},
                created_at=utc_now(),
            )
        )

    def _apply_filters(
        self,
        stmt: Select[tuple[AssetORM]],
        filters: AssetSearchFilter,
    ) -> Select[tuple[AssetORM]]:
        if filters.asset_types:
            stmt = stmt.where(
                AssetORM.asset_type.in_([t.value for t in filters.asset_types])
            )
        if filters.statuses:
            stmt = stmt.where(
                AssetORM.status.in_([s.value for s in filters.statuses])
            )
        if filters.business_unit_id:
            stmt = stmt.where(AssetORM.business_unit_id == filters.business_unit_id)
        if filters.environment_id:
            stmt = stmt.where(AssetORM.environment_id == filters.environment_id)
        if filters.cloud_providers:
            stmt = stmt.where(
                AssetORM.cloud_provider.in_(
                    [p.value for p in filters.cloud_providers]
                )
            )
        if filters.criticality_tiers:
            stmt = stmt.where(
                AssetORM.criticality_tier.in_(
                    [t.value for t in filters.criticality_tiers]
                )
            )
        if filters.exposure_levels:
            stmt = stmt.where(
                AssetORM.exposure_level.in_(
                    [e.value for e in filters.exposure_levels]
                )
            )
        if filters.internet_facing_only:
            stmt = stmt.where(
                AssetORM.exposure_level == ExposureLevel.PUBLIC_INTERNET.value
            )
        if filters.crown_jewel_only:
            stmt = stmt.where(AssetORM.crown_jewel.is_(True))
        if filters.text:
            pattern = f"%{filters.text.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(AssetORM.name).like(pattern),
                    func.lower(func.coalesce(AssetORM.hostname, "")).like(pattern),
                    func.lower(func.coalesce(AssetORM.external_id, "")).like(pattern),
                    func.lower(func.coalesce(AssetORM.fqdn, "")).like(pattern),
                )
            )
        if filters.compliance_tags:
            for tag in filters.compliance_tags:
                stmt = stmt.where(
                    cast(AssetORM.payload["compliance_tags"], String).like(
                        f'%"{tag.lower()}"%'
                    )
                )
        if filters.tags:
            for key, value in filters.tags.items():
                stmt = stmt.where(
                    cast(AssetORM.payload["tags"][key], String).like(f'%{value}%')
                )
        if filters.environment_kinds:
            # Join via environments table when kinds requested.
            env_ids = select(EnvironmentORM.id).where(
                EnvironmentORM.tenant_id == filters.tenant_id,
                EnvironmentORM.kind.in_(
                    [k.value for k in filters.environment_kinds]
                ),
            )
            stmt = stmt.where(AssetORM.environment_id.in_(env_ids))
        return stmt
