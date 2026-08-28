"""
Enterprise Risk Engine
======================

Calculates the **Enterprise Risk Score** (0–100) for every
``SecurityFindingObject`` after Trust Scoring and before the Decision Service.

Consumes assembled snapshots from:

- Evidence Repository
- Asset Inventory
- Threat Intelligence
- Trust Scoring Engine

## Non-goals

- No REST APIs yet
- No AI / LLM calls
- No external API calls
- Does not modify ``SecurityFindingObject`` or other existing modules
- Does not replace Trust Scoring (trust is an *input* pillar)

## Quick start

```python
from uuid import uuid4
from risk_engine import (
    RiskEngineContainer,
    RiskScoringInput,
    BusinessContext,
    ComplianceFramework,
)
from risk_engine.domain.inputs import (
    FindingRiskBaselineInput,
    TrustRiskInput,
    CvssInput,
    ThreatIntelRiskInput,
    AssetRiskInput,
)

container = RiskEngineContainer.from_url(
    "postgresql+psycopg://user:pass@localhost:5432/xolaris",
    create_tables=True,
)

finding_id = uuid4()
tenant_id = uuid4()
asset_id = uuid4()

scoring_input = RiskScoringInput(
    finding=FindingRiskBaselineInput(
        finding_id=finding_id,
        tenant_id=tenant_id,
        asset_id=asset_id,
        finding_age_days=5.0,
    ),
    trust=TrustRiskInput(trust_score=82.0, trust_level="high"),
    cvss=CvssInput(version="3.1", base_score=9.8),
    threat_intel=ThreatIntelRiskInput(
        enrichment_present=True,
        epss_score=0.85,
        in_cisa_kev=True,
        actively_exploited=True,
        mitre_technique_count=2,
        ioc_match_count=1,
        max_ioc_confidence=0.9,
    ),
    asset=AssetRiskInput(
        asset_id=asset_id,
        asset_criticality=0.9,
        business_criticality=0.85,
        environments=[BusinessContext.PRODUCTION, BusinessContext.INTERNET_FACING],
        internet_facing=True,
        customer_facing=True,
        compliance_tags=[ComplianceFramework.PCI, ComplianceFramework.SOC2],
    ),
)

with container.session() as session:
    svc = container.build(session)
    assessment = svc.risk_engine.score(scoring_input)
    print(assessment.enterprise_risk_score.value, assessment.risk_level)
    print(assessment.priority, assessment.recommended_sla)
```

## Pure compute (no persistence)

```python
from unittest.mock import MagicMock
from risk_engine.services.risk_engine_service import RiskEngineService

svc = RiskEngineService(MagicMock())
assessment = svc.compute(scoring_input)
```

## Layout

```
risk_engine/
  domain/         # models, inputs, weights, history, enums, builders
  interfaces/     # Risk / History repository ports
  persistence/    # SQLAlchemy ORM + Postgres repos
  services/       # technical / business / compliance / exposure / aggregation / facade
  query/          # filters + pagination
  di/             # composition root
```

## Risk levels & SLA

| Score | Level | Priority | SLA |
|------:|-------|----------|-----|
| 90–100 | Critical | P1 | Immediate |
| 70–89 | High | P2 | 24 Hours |
| 40–69 | Medium | P3 | 7 Days |
| 20–39 | Low | P4 | 30 Days |
| 0–19 | Informational | P5 | Monitor |

## Architecture doc

See ``docs/architecture/13-risk-engine.md``.
"""
