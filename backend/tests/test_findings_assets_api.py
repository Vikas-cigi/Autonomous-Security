"""HTTP tests for Findings and Asset Inventory APIs."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app import app
from asset_inventory import AssetInventoryContainer
from asset_inventory.domain.enums import AssetType
from asset_inventory.domain.models import Asset
from evidence_repository import EvidenceRepositoryContainer
from models.common import ActorReference, new_id
from models.enums import (
    EvidenceSource,
    EvidenceValidationStatus,
    FindingStatus,
    FindingType,
    HashAlgorithm,
    Severity,
    SourceTool,
)
from models.evidence import ContentHash, EvidenceLineage, EvidenceObject
from models.security_finding import SecurityFindingObject
from scan_ingest import ScanIngestContainer, ScanMode, ScanRequest


def _sqlite_url() -> tuple[str, str]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return "sqlite+pysqlite:///" + Path(path).as_posix(), path


def _evidence() -> EvidenceObject:
    return EvidenceObject(
        id=new_id(),
        raw_artifact_id=new_id(),
        summary="Scanner evidence summary for API test",
        source=EvidenceSource.SCANNER,
        confidence=0.9,
        hash=ContentHash(algorithm=HashAlgorithm.SHA256, value="b" * 64),
        lineage=EvidenceLineage(source_tool=SourceTool.NUCLEI),
        validation_status=EvidenceValidationStatus.VALIDATED,
    )


def _finding(**kwargs) -> SecurityFindingObject:
    tenant = kwargs.pop("tenant_id", uuid4())
    asset = kwargs.pop("asset_id", uuid4())
    base = dict(
        tenant_id=tenant,
        asset_id=asset,
        source_tool=SourceTool.NUCLEI,
        finding_type=FindingType.VULNERABILITY,
        severity=Severity.HIGH,
        cvss_score=8.0,
        confidence_score=0.85,
        evidence=[_evidence()],
        title="Remote code execution via template match",
        description="Nuclei matched an RCE template on the asset.",
        cve_ids=["CVE-2021-44228"],
        status=FindingStatus.NEW,
    )
    base.update(kwargs)
    return SecurityFindingObject(**base)


class FindingsAPITests(unittest.TestCase):
    def setUp(self) -> None:
        url, self._db_path = _sqlite_url()
        self.container = EvidenceRepositoryContainer.from_url(
            url, create_tables=True
        )
        self.tenant_id = uuid4()
        finding = _finding(tenant_id=self.tenant_id)
        with self.container.session() as session:
            svc = self.container.build(session)
            saved = svc.repository.save_finding(finding, actor="api-test")
            self.finding_id = saved.id
        self._patch = patch(
            "api.v1.findings.get_evidence_container",
            return_value=self.container,
        )
        self._patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._patch.stop()
        self.container.session_factory.engine.dispose()
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_search_and_get_finding(self) -> None:
        listed = self.client.get(
            "/api/v1/findings",
            params={"tenant_id": str(self.tenant_id)},
        )
        self.assertEqual(listed.status_code, 200)
        body = listed.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["total_items"], 1)
        self.assertEqual(body["data"]["items"][0]["id"], str(self.finding_id))

        fetched = self.client.get(
            f"/api/v1/findings/{self.finding_id}",
            params={"tenant_id": str(self.tenant_id)},
        )
        self.assertEqual(fetched.status_code, 200)
        detail = fetched.json()
        self.assertTrue(detail["success"])
        self.assertEqual(
            detail["data"]["title"],
            "Remote code execution via template match",
        )
        self.assertEqual(len(detail["data"]["evidence"]), 1)

        history = self.client.get(
            f"/api/v1/findings/{self.finding_id}/history",
            params={"tenant_id": str(self.tenant_id)},
        )
        self.assertEqual(history.status_code, 200)
        self.assertGreaterEqual(len(history.json()["data"]), 1)

    def test_search_filters_by_severity(self) -> None:
        listed = self.client.get(
            "/api/v1/findings",
            params={"tenant_id": str(self.tenant_id), "severity": "low"},
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["data"]["total_items"], 0)

    def test_get_finding_unknown_is_not_found(self) -> None:
        missing = uuid4()
        fetched = self.client.get(
            f"/api/v1/findings/{missing}",
            params={"tenant_id": str(self.tenant_id)},
        )
        self.assertEqual(fetched.status_code, 200)
        body = fetched.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "FindingNotFoundError")

    def test_get_finding_wrong_tenant_is_not_found(self) -> None:
        fetched = self.client.get(
            f"/api/v1/findings/{self.finding_id}",
            params={"tenant_id": str(uuid4())},
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertFalse(fetched.json()["success"])


class AssetsAPITests(unittest.TestCase):
    def setUp(self) -> None:
        url, self._db_path = _sqlite_url()
        self.container = AssetInventoryContainer.from_url(url, create_tables=True)
        self.tenant_id = uuid4()
        asset = Asset(
            tenant_id=self.tenant_id,
            name="web-prod-01",
            asset_type=AssetType.EC2,
            external_id="i-0api123",
            hostname="web-prod-01.internal",
        )
        with self.container.session() as session:
            svc = self.container.build(session)
            saved = svc.assets.register_asset(asset, actor="api-test")
            self.asset_id = saved.id
        self._patch = patch(
            "api.v1.assets.get_asset_container",
            return_value=self.container,
        )
        self._patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._patch.stop()
        self.container.session_factory.engine.dispose()
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_search_and_get_asset(self) -> None:
        listed = self.client.get(
            "/api/v1/assets",
            params={"tenant_id": str(self.tenant_id)},
        )
        self.assertEqual(listed.status_code, 200)
        body = listed.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["total_items"], 1)
        self.assertEqual(body["data"]["items"][0]["id"], str(self.asset_id))

        fetched = self.client.get(
            f"/api/v1/assets/{self.asset_id}",
            params={"tenant_id": str(self.tenant_id)},
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["data"]["name"], "web-prod-01")

    def test_get_asset_unknown_is_not_found(self) -> None:
        fetched = self.client.get(
            f"/api/v1/assets/{uuid4()}",
            params={"tenant_id": str(self.tenant_id)},
        )
        self.assertEqual(fetched.status_code, 200)
        body = fetched.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "AssetNotFoundError")


class ScanThenQueryAPITests(unittest.TestCase):
    """Scan ingest and findings/assets APIs share the same containers."""

    def setUp(self) -> None:
        url, self._db_path = _sqlite_url()
        self.evidence = EvidenceRepositoryContainer.from_url(
            url, create_tables=True
        )
        self.assets = AssetInventoryContainer.from_url(url, create_tables=True)
        self.scan = ScanIngestContainer(self.assets, self.evidence)
        self.tenant_id = uuid4()
        request = ScanRequest(
            tenant_id=self.tenant_id,
            target="https://demo.xolaris.local",
            tool_name="nuclei",
            mode=ScanMode.SIMULATE,
            actor=ActorReference(actor_id=uuid4(), display_name="api-tester"),
            run_pipeline=False,
        )
        with self.scan.session_scope(enable_pipeline=False) as svc:
            self.scan_result = svc.engine.scan(request)
        self._finding_patch = patch(
            "api.v1.findings.get_evidence_container",
            return_value=self.evidence,
        )
        self._asset_patch = patch(
            "api.v1.assets.get_asset_container",
            return_value=self.assets,
        )
        self._finding_patch.start()
        self._asset_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._finding_patch.stop()
        self._asset_patch.stop()
        self.evidence.session_factory.engine.dispose()
        self.assets.session_factory.engine.dispose()
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_simulated_scan_is_visible_via_http(self) -> None:
        self.assertGreaterEqual(self.scan_result.findings_created, 1)
        listed = self.client.get(
            "/api/v1/findings",
            params={"tenant_id": str(self.tenant_id)},
        )
        self.assertEqual(listed.status_code, 200)
        self.assertGreaterEqual(listed.json()["data"]["total_items"], 1)

        assets = self.client.get(
            "/api/v1/assets",
            params={"tenant_id": str(self.tenant_id)},
        )
        self.assertEqual(assets.status_code, 200)
        self.assertGreaterEqual(assets.json()["data"]["total_items"], 1)


if __name__ == "__main__":
    unittest.main()
