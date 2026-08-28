"""Unit tests for Evidence Repository (SQLite)."""

from __future__ import annotations

import unittest
from uuid import uuid4

from models.common import new_id
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

from evidence_repository import EvidenceRepositoryContainer
from evidence_repository.domain.enums import LifecycleState
from evidence_repository.query.filters import FindingSearchFilter
from evidence_repository.query.pagination import PageRequest


def _evidence() -> EvidenceObject:
    return EvidenceObject(
        id=new_id(),
        raw_artifact_id=new_id(),
        summary="Scanner evidence summary for repository test",
        source=EvidenceSource.SCANNER,
        confidence=0.9,
        hash=ContentHash(algorithm=HashAlgorithm.SHA256, value="a" * 64),
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


class EvidenceRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = EvidenceRepositoryContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )

    def test_save_get_version_and_search(self) -> None:
        finding = _finding()
        with self.container.session() as session:
            svc = self.container.build(session)
            saved = svc.repository.save_finding(finding, actor="test")
            loaded = svc.repository.get_finding(saved.id, saved.tenant_id)
            self.assertEqual(loaded.title, finding.title)
            versions = svc.repository.list_finding_versions(saved.id, saved.tenant_id)
            self.assertEqual(len(versions), 1)
            page = svc.search.search(
                FindingSearchFilter(
                    tenant_id=saved.tenant_id,
                    severities=[Severity.HIGH],
                    scanners=[SourceTool.NUCLEI],
                ),
                PageRequest(page=1, page_size=10),
            )
            self.assertEqual(page.total_items, 1)
            self.assertEqual(page.items[0].id, saved.id)

    def test_deduplication_merges(self) -> None:
        tenant = uuid4()
        asset = uuid4()
        first = _finding(tenant_id=tenant, asset_id=asset)
        second = _finding(
            tenant_id=tenant,
            asset_id=asset,
            title=first.title,
            cve_ids=first.cve_ids,
            evidence=[_evidence()],
        )
        with self.container.session() as session:
            svc = self.container.build(session)
            r1 = svc.deduplication.ingest(first, actor="test")
            r2 = svc.deduplication.ingest(second, actor="test")
            self.assertTrue(r1.created)
            self.assertFalse(r2.created)
            self.assertEqual(r2.merged_into_id, r1.finding.id)
            versions = svc.repository.list_finding_versions(
                r1.finding.id, tenant
            )
            self.assertGreaterEqual(len(versions), 2)
            merged = svc.repository.get_finding(r1.finding.id, tenant)
            self.assertEqual(len(merged.evidence), 2)

    def test_lifecycle_update_and_tenant_isolation(self) -> None:
        finding = _finding()
        with self.container.session() as session:
            svc = self.container.build(session)
            saved = svc.repository.save_finding(finding)
            updated = svc.repository.update_lifecycle(
                saved.id,
                saved.tenant_id,
                LifecycleState.RESOLVED,
                actor="analyst",
            )
            self.assertEqual(updated.status, FindingStatus.RESOLVED)
            history = svc.repository.list_finding_history(saved.id, saved.tenant_id)
            self.assertTrue(any(h.to_status == FindingStatus.RESOLVED for h in history))
            other_tenant = uuid4()
            with self.assertRaises(Exception):
                svc.repository.get_finding(saved.id, other_tenant)

    def test_correlation_groups_across_scanners(self) -> None:
        tenant = uuid4()
        asset = uuid4()
        a = _finding(
            tenant_id=tenant,
            asset_id=asset,
            source_tool=SourceTool.NUCLEI,
            title="Log4Shell",
            cve_ids=["CVE-2021-44228"],
        )
        b = _finding(
            tenant_id=tenant,
            asset_id=asset,
            source_tool=SourceTool.TRIVY,
            title="log4j critical",
            cve_ids=["CVE-2021-44228"],
        )
        with self.container.session() as session:
            svc = self.container.build(session)
            groups = svc.correlation.correlate_findings(
                tenant, [a, b], actor="corr", min_group_size=2
            )
            self.assertEqual(len(groups), 1)
            members = svc.correlation.get_group(
                tenant, groups[0].correlation_group_id
            )
            self.assertEqual(len(members), 2)


if __name__ == "__main__":
    unittest.main()
