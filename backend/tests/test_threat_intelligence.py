"""Unit tests for Threat Intelligence Service (SQLite)."""

from __future__ import annotations

import unittest
from uuid import uuid4

from threat_intelligence import ThreatIntelligenceContainer
from threat_intelligence.domain.enums import (
    CVSSVersion,
    ExploitMaturity,
    FeedSyncStatus,
    IOCType,
    ThreatFeedProviderId,
)
from threat_intelligence.domain.ioc import IndicatorOfCompromise
from threat_intelligence.domain.models import (
    CVERecord,
    CVSSMetric,
    EPSSScore,
    ExploitInformation,
    MITRETechnique,
    ThreatActor,
    ThreatFeedMetadata,
)
from threat_intelligence.query.filters import ThreatIntelSearchFilter
from threat_intelligence.query.pagination import PageRequest


class ThreatIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = ThreatIntelligenceContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )
        self.tenant = uuid4()

    def test_cve_enrichment_and_finding_enrich(self) -> None:
        finding_id = uuid4()
        with self.container.session() as session:
            svc = self.container.build(session)
            svc.cve_enrichment.upsert_cve(
                CVERecord(
                    cve_id="CVE-2021-44228",
                    title="Log4Shell",
                    description="Remote code execution in Log4j",
                    cvss_metrics=[
                        CVSSMetric(
                            version=CVSSVersion.V3_1,
                            base_score=10.0,
                            vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                            severity="CRITICAL",
                        )
                    ],
                    epss=EPSSScore(score=0.975, percentile=0.99),
                    exploit=ExploitInformation(
                        available=True,
                        maturity=ExploitMaturity.HIGH,
                        actively_exploited=True,
                        in_cisa_kev=True,
                    ),
                    cwe_ids=["CWE-502"],
                    mitre_techniques=[
                        MITRETechnique(technique_id="T1190", name="Exploit Public-Facing Application")
                    ],
                    source_providers=[ThreatFeedProviderId.MANUAL],
                    confidence_score=0.95,
                ),
                actor="test",
            )
            intel = svc.intelligence.enrich_finding(
                tenant_id=self.tenant,
                finding_id=finding_id,
                cve_ids=["CVE-2021-44228"],
                technique_ids=["T1059.001"],
                actor="test",
            )
            self.assertEqual(intel.finding_id, finding_id)
            self.assertTrue(intel.exploit.in_cisa_kev)
            self.assertTrue(intel.exploit.actively_exploited)
            self.assertIsNotNone(intel.epss)
            self.assertIn("CWE-502", intel.cwe_ids)
            tech_ids = {t.technique_id for t in intel.mitre_techniques}
            self.assertIn("T1190", tech_ids)
            self.assertIn("T1059.001", tech_ids)
            versions = svc.intel_repository.list_versions(intel.id, self.tenant)
            self.assertGreaterEqual(len(versions), 1)

    def test_ioc_correlation_and_actor_attach(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            ioc = svc.ioc_correlation.upsert_ioc(
                IndicatorOfCompromise.from_raw(
                    ioc_type=IOCType.DOMAIN,
                    value="evil.example.com",
                    tenant_id=self.tenant,
                    cve_ids=["CVE-2021-44228"],
                    confidence_score=0.9,
                ),
                actor="test",
            )
            intel = svc.intelligence.get_or_create_for_finding(
                tenant_id=self.tenant,
                finding_id=uuid4(),
                actor="test",
            )
            intel = svc.ioc_correlation.apply_to_intelligence(
                intel,
                ["evil.example.com", "benign.example.com"],
                actor="test",
            )
            self.assertIn(ioc.id, intel.ioc_ids)
            self.assertIn("CVE-2021-44228", intel.cve_ids)

            actor = ThreatActor(
                tenant_id=self.tenant,
                name="Example APT",
                aliases=["APT-X"],
            )
            intel = svc.intelligence.attach_threat_actor(
                intel.id, self.tenant, actor, actor="analyst"
            )
            self.assertEqual(len(intel.threat_actors), 1)

    def test_feed_sync_placeholder_skipped(self) -> None:
        with self.container.session() as session:
            svc = self.container.build(session)
            feed = svc.feed_sync.register_feed(
                ThreatFeedMetadata(
                    tenant_id=self.tenant,
                    provider=ThreatFeedProviderId.NVD,
                    name="NVD placeholder",
                    enabled=True,
                ),
                actor="test",
            )
            result = svc.feed_sync.sync_feed(feed.id, tenant_id=self.tenant)
            self.assertEqual(result.status, FeedSyncStatus.SKIPPED)
            self.assertEqual(len(svc.provider_registry.list_providers()), 8)
            updated = svc.feed_repository.get_feed(feed.id)
            self.assertEqual(updated.last_sync_status, FeedSyncStatus.SKIPPED.value)

    def test_tenant_isolation_on_search(self) -> None:
        other = uuid4()
        with self.container.session() as session:
            svc = self.container.build(session)
            svc.intelligence.get_or_create_for_finding(
                tenant_id=self.tenant,
                finding_id=uuid4(),
            )
            page = svc.intelligence.search(
                ThreatIntelSearchFilter(tenant_id=other),
                PageRequest(),
            )
            self.assertEqual(page.total_items, 0)


if __name__ == "__main__":
    unittest.main()
