"""
Enterprise Threat Intelligence Service
======================================

Intelligence layer between the Evidence Repository and the (future) Risk Engine.

Enriches findings by ``finding_id`` with CVE / CVSS / EPSS / CISA KEV, MITRE,
CAPEC, CWE, exploit posture, IOCs, actors, malware, and campaigns.

## Non-goals

- No REST APIs yet
- No live external API integrations (NVD, KEV, MISP, …) — placeholders only
- Does not modify SecurityFindingObject or other existing modules

## Quick start

```python
from uuid import uuid4
from threat_intelligence import ThreatIntelligenceContainer, CVERecord
from threat_intelligence.domain.enums import CVSSVersion, ThreatFeedProviderId
from threat_intelligence.domain.models import CVSSMetric, ExploitInformation, EPSSScore

container = ThreatIntelligenceContainer.from_url(
    "postgresql+psycopg://user:pass@localhost:5432/xolaris",
    create_tables=True,
)

with container.session() as session:
    svc = container.build(session)
    svc.cve_enrichment.upsert_cve(
        CVERecord(
            cve_id="CVE-2021-44228",
            title="Log4Shell",
            cvss_metrics=[CVSSMetric(version=CVSSVersion.V3_1, base_score=10.0)],
            epss=EPSSScore(score=0.97),
            exploit=ExploitInformation(in_cisa_kev=True, actively_exploited=True),
            source_providers=[ThreatFeedProviderId.MANUAL],
        )
    )
    intel = svc.intelligence.enrich_finding(
        tenant_id=uuid4(),
        finding_id=uuid4(),
        cve_ids=["CVE-2021-44228"],
        technique_ids=["T1190"],
    )
```

## Layout

```
threat_intelligence/
  domain/         # models, IOC, history, enums
  providers/      # ThreatFeedProvider ABC + placeholders
  interfaces/     # repository ports
  persistence/    # SQLAlchemy ORM + repos
  services/       # enrichment / sync / correlation
  query/          # filters + pagination
  di/             # composition root
```

## Architecture doc

See ``docs/architecture/11-threat-intelligence.md``.
"""
