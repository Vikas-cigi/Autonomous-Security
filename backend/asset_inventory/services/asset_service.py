"""Application service for Asset Inventory use cases."""

from __future__ import annotations

from typing import Dict, List, Optional
from uuid import UUID

from asset_inventory.domain.enums import (
    AssetStatus,
    AssetType,
    AuditAction,
    EnvironmentKind,
)
from asset_inventory.domain.models import (
    Asset,
    AssetOwner,
    AssetRelationship,
    BusinessUnit,
    Environment,
)
from asset_inventory.domain.scoring import CriticalityScore, CriticalityScorer
from asset_inventory.interfaces.repository import AssetRepository
from asset_inventory.query.filters import AssetSearchFilter
from asset_inventory.query.pagination import Page, PageRequest
from asset_inventory.services.audit import AuditLogger


class AssetService:
    """
    Application service — scoring, upsert-by-external-id, tagging, search.

    Depends on ``AssetRepository`` (DIP); no persistence details here.
    """

    def __init__(
        self,
        repository: AssetRepository,
        *,
        scorer: Optional[CriticalityScorer] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._repo = repository
        self._scorer = scorer or CriticalityScorer()
        self._audit = audit_logger

    def register_asset(
        self,
        asset: Asset,
        *,
        actor: Optional[str] = None,
        environment_kind: Optional[EnvironmentKind] = None,
    ) -> Asset:
        """
        Persist a new or updated asset with criticality scoring applied.

        If ``external_id`` matches an existing asset, merge onto that identity.
        """

        if asset.external_id:
            existing = self._repo.find_by_external_id(
                asset.tenant_id, asset.external_id
            )
            if existing is not None:
                asset.id = existing.id
                asset.created_at = existing.created_at
                asset.current_version = existing.current_version

        kind = environment_kind
        if kind is None and asset.environment_id is not None:
            try:
                env = self._repo.get_environment(
                    asset.environment_id, asset.tenant_id
                )
                kind = env.kind
            except Exception:
                kind = None

        score = self.apply_criticality(asset, environment_kind=kind)
        asset.criticality_score = score.score
        asset.classification.criticality_tier = score.tier
        return self._repo.save_asset(
            asset,
            actor=actor,
            change_summary="Asset registered",
        )

    def apply_criticality(
        self,
        asset: Asset,
        *,
        environment_kind: Optional[EnvironmentKind] = None,
    ) -> CriticalityScore:
        """Compute and optionally return criticality without persisting."""

        return self._scorer.score(
            asset.classification,
            environment_kind=environment_kind,
        )

    def recompute_criticality(
        self,
        asset_id: UUID,
        tenant_id: UUID,
        *,
        actor: Optional[str] = None,
    ) -> Asset:
        """Reload asset, recompute score, persist a new version."""

        asset = self._repo.get_asset(asset_id, tenant_id)
        kind: Optional[EnvironmentKind] = None
        if asset.environment_id is not None:
            env = self._repo.get_environment(asset.environment_id, tenant_id)
            kind = env.kind
        score = self.apply_criticality(asset, environment_kind=kind)
        asset.criticality_score = score.score
        asset.classification.criticality_tier = score.tier
        saved = self._repo.save_asset(
            asset,
            actor=actor,
            change_summary="Criticality recomputed",
        )
        if self._audit:
            self._audit.log(
                tenant_id=tenant_id,
                action=AuditAction.SCORE_RECOMPUTED,
                message="Criticality recomputed",
                actor=actor,
                details={
                    "asset_id": str(asset_id),
                    "score": score.score,
                    "tier": score.tier.value,
                },
            )
        return saved

    def set_tags(
        self,
        asset_id: UUID,
        tenant_id: UUID,
        tags: Dict[str, str],
        *,
        merge: bool = True,
        actor: Optional[str] = None,
    ) -> Asset:
        """Replace or merge inventory tags."""

        asset = self._repo.get_asset(asset_id, tenant_id)
        if merge:
            merged = dict(asset.tags)
            merged.update(tags)
            asset.tags = merged
        else:
            asset.tags = tags
        return self._repo.save_asset(
            asset,
            actor=actor,
            change_summary="Tags updated",
        )

    def set_compliance_tags(
        self,
        asset_id: UUID,
        tenant_id: UUID,
        compliance_tags: List[str],
        *,
        actor: Optional[str] = None,
    ) -> Asset:
        """Set compliance tags on asset + classification."""

        asset = self._repo.get_asset(asset_id, tenant_id)
        asset.compliance_tags = compliance_tags
        asset.classification.compliance_tags = list(compliance_tags)
        if compliance_tags:
            asset.classification.regulated = True
        return self._repo.save_asset(
            asset,
            actor=actor,
            change_summary="Compliance tags updated",
        )

    def assign_owners(
        self,
        asset_id: UUID,
        tenant_id: UUID,
        owners: List[AssetOwner],
        *,
        actor: Optional[str] = None,
    ) -> Asset:
        return self._repo.set_owners(asset_id, tenant_id, owners, actor=actor)

    def link_assets(
        self,
        relationship: AssetRelationship,
        *,
        actor: Optional[str] = None,
    ) -> AssetRelationship:
        return self._repo.save_relationship(relationship, actor=actor)

    def search(
        self,
        filters: AssetSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[Asset]:
        return self._repo.search_assets(filters, page or PageRequest())

    def list_by_type(
        self,
        tenant_id: UUID,
        asset_type: AssetType,
        *,
        page: Optional[PageRequest] = None,
    ) -> Page[Asset]:
        return self.search(
            AssetSearchFilter(
                tenant_id=tenant_id,
                asset_types=[asset_type],
                statuses=[AssetStatus.ACTIVE],
            ),
            page,
        )

    def ensure_business_unit(
        self,
        unit: BusinessUnit,
        *,
        actor: Optional[str] = None,
    ) -> BusinessUnit:
        return self._repo.save_business_unit(unit, actor=actor)

    def ensure_environment(
        self,
        environment: Environment,
        *,
        actor: Optional[str] = None,
    ) -> Environment:
        return self._repo.save_environment(environment, actor=actor)

    def get(self, asset_id: UUID, tenant_id: UUID) -> Asset:
        return self._repo.get_asset(asset_id, tenant_id)
