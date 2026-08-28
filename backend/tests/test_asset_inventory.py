"""Unit tests for Asset Inventory (SQLite)."""

from __future__ import annotations

import unittest
from uuid import uuid4

from asset_inventory import AssetInventoryContainer
from asset_inventory.domain.classification import (
    AssetClassification,
    InternetExposure,
)
from asset_inventory.domain.enums import (
    AssetStatus,
    AssetType,
    CriticalityTier,
    DataSensitivity,
    EnvironmentKind,
    ExposureLevel,
    RelationshipType,
)
from asset_inventory.domain.metadata import CloudMetadata, KubernetesMetadata
from asset_inventory.domain.models import (
    Asset,
    AssetOwner,
    AssetRelationship,
    BusinessUnit,
    Environment,
)
from asset_inventory.exceptions import AssetNotFoundError
from asset_inventory.query.filters import AssetSearchFilter
from asset_inventory.query.pagination import PageRequest


class AssetInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = AssetInventoryContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )
        self.tenant = uuid4()

    def test_register_score_version_and_search(self) -> None:
        asset = Asset(
            tenant_id=self.tenant,
            name="web-prod-01",
            asset_type=AssetType.EC2,
            external_id="i-0abc123",
            hostname="web-prod-01.internal",
            classification=AssetClassification(
                business_criticality=CriticalityTier.HIGH,
                data_sensitivity=DataSensitivity.CONFIDENTIAL,
                internet_exposure=InternetExposure(
                    level=ExposureLevel.PUBLIC_INTERNET,
                    public_ips=["203.0.113.10"],
                    open_ports=[443],
                ),
                compliance_tags=["pci-dss"],
                regulated=True,
            ),
            cloud=CloudMetadata(account_id="123456789012", region="us-east-1"),
            tags={"app": "payments", "tier": "web"},
        )
        with self.container.session() as session:
            svc = self.container.build(session)
            saved = svc.assets.register_asset(asset, actor="test")
            self.assertGreaterEqual(saved.criticality_score, 0.65)
            self.assertEqual(saved.cloud.provider.value, "aws")
            loaded = svc.assets.get(saved.id, self.tenant)
            self.assertEqual(loaded.external_id, "i-0abc123")
            versions = svc.repository.list_asset_versions(saved.id, self.tenant)
            self.assertEqual(len(versions), 1)
            page = svc.assets.search(
                AssetSearchFilter(
                    tenant_id=self.tenant,
                    asset_types=[AssetType.EC2],
                    internet_facing_only=True,
                ),
                PageRequest(page=1, page_size=10),
            )
            self.assertEqual(page.total_items, 1)

    def test_upsert_by_external_id_and_tags(self) -> None:
        first = Asset(
            tenant_id=self.tenant,
            name="api-gw",
            asset_type=AssetType.API_GATEWAY,
            external_id="arn:aws:apigateway:us-east-1::/restapis/abc",
        )
        with self.container.session() as session:
            svc = self.container.build(session)
            a1 = svc.assets.register_asset(first, actor="sync")
            second = Asset(
                tenant_id=self.tenant,
                name="api-gw-renamed",
                asset_type=AssetType.API_GATEWAY,
                external_id=first.external_id,
            )
            a2 = svc.assets.register_asset(second, actor="sync")
            self.assertEqual(a1.id, a2.id)
            self.assertEqual(a2.name, "api-gw-renamed")
            versions = svc.repository.list_asset_versions(a1.id, self.tenant)
            self.assertGreaterEqual(len(versions), 2)
            tagged = svc.assets.set_tags(
                a1.id, self.tenant, {"env": "prod"}, actor="ops"
            )
            self.assertEqual(tagged.tags["env"], "prod")

    def test_org_owners_relationships_and_tenant_isolation(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            bu = svc.assets.ensure_business_unit(
                BusinessUnit(tenant_id=self.tenant, name="Payments", code="PAY")
            )
            env = svc.assets.ensure_environment(
                Environment(
                    tenant_id=self.tenant,
                    name="production",
                    kind=EnvironmentKind.PRODUCTION,
                )
            )
            host = svc.assets.register_asset(
                Asset(
                    tenant_id=self.tenant,
                    name="k8s-node-1",
                    asset_type=AssetType.KUBERNETES,
                    business_unit_id=bu.id,
                    environment_id=env.id,
                    kubernetes=KubernetesMetadata(
                        cluster_name="prod-east",
                        namespace="payments",
                        kind="Node",
                        name="ip-10-0-1-5",
                    ),
                )
            )
            pod = svc.assets.register_asset(
                Asset(
                    tenant_id=self.tenant,
                    name="payments-api",
                    asset_type=AssetType.KUBERNETES,
                    environment_id=env.id,
                    kubernetes=KubernetesMetadata(
                        cluster_name="prod-east",
                        namespace="payments",
                        kind="Deployment",
                        name="payments-api",
                        container_images=["payments-api:1.2.3"],
                    ),
                )
            )
            svc.assets.assign_owners(
                host.id,
                self.tenant,
                [
                    AssetOwner(
                        tenant_id=self.tenant,
                        display_name="SRE Oncall",
                        email="sre@example.com",
                        owner_type="team",
                    )
                ],
            )
            rel = svc.assets.link_assets(
                AssetRelationship(
                    tenant_id=self.tenant,
                    source_asset_id=pod.id,
                    target_asset_id=host.id,
                    relationship_type=RelationshipType.DEPENDS_ON,
                )
            )
            self.assertTrue(rel.is_active)
            edges = svc.repository.list_relationships(
                self.tenant, asset_id=pod.id
            )
            self.assertEqual(len(edges), 1)
            with self.assertRaises(AssetNotFoundError):
                svc.assets.get(host.id, uuid4())

    def test_soft_decommission_and_history(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            asset = svc.assets.register_asset(
                Asset(
                    tenant_id=self.tenant,
                    name="legacy-rds",
                    asset_type=AssetType.RDS,
                    external_id="db-legacy-1",
                )
            )
            gone = svc.repository.delete_asset(
                asset.id, self.tenant, actor="ops", soft=True
            )
            self.assertEqual(gone.status, AssetStatus.DECOMMISSIONED)
            history = svc.repository.list_asset_history(asset.id, self.tenant)
            self.assertTrue(len(history) >= 2)


if __name__ == "__main__":
    unittest.main()
