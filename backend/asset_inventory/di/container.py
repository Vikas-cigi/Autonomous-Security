"""Dependency injection container for Asset Inventory."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from asset_inventory.domain.scoring import CriticalityScorer
from asset_inventory.interfaces.repository import AssetRepository
from asset_inventory.persistence.postgres_repository import PostgresAssetRepository
from asset_inventory.persistence.session import SessionFactory
from asset_inventory.services.asset_service import AssetService
from asset_inventory.services.audit import AuditLogger


@dataclass
class AssetInventoryContainer:
    """
    Composition root for repository + AssetService.

    Example::

        container = AssetInventoryContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            services = container.build(session)
            services.assets.register_asset(asset)
    """

    session_factory: SessionFactory

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> AssetInventoryContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            )
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "AssetInventoryServices":
        audit = AuditLogger(session)
        repository: AssetRepository = PostgresAssetRepository(
            session, audit_logger=audit
        )
        return AssetInventoryServices(
            repository=repository,
            audit=audit,
            assets=AssetService(
                repository,
                scorer=CriticalityScorer(),
                audit_logger=audit,
            ),
        )


@dataclass
class AssetInventoryServices:
    """Bundled services sharing one unit-of-work session."""

    repository: AssetRepository
    audit: AuditLogger
    assets: AssetService
