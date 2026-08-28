"""
Enterprise Trust Scoring Engine
===============================

Evaluates the confidence and reliability of every ``SecurityFindingObject``
before it reaches the Risk Engine. Reduces false positives and improves
remediation decisions via a normalized Trust Score (0–100).

## Non-goals

- No REST APIs yet
- No AI / LLM calls
- No external API calls
- Does not modify ``SecurityFindingObject`` or other existing modules
- Does not replace the (future) Risk Engine

## Quick start

```python
from uuid import uuid4
from models.enums import SourceTool
from trust_scoring import TrustScoringContainer, TrustScoringInput
from trust_scoring.domain.inputs import FindingBaselineInput, EvidenceItemInput

container = TrustScoringContainer.from_url(
    "postgresql+psycopg://user:pass@localhost:5432/xolaris",
    create_tables=True,
)

finding_id = uuid4()
tenant_id = uuid4()
asset_id = uuid4()

scoring_input = TrustScoringInput(
    finding=FindingBaselineInput(
        finding_id=finding_id,
        tenant_id=tenant_id,
        asset_id=asset_id,
        source_tool=SourceTool.NESSUS,
        finding_confidence=0.8,
        evidence_count=2,
        has_cve=True,
        finding_age_days=3.0,
    ),
    evidence_items=[
        EvidenceItemInput(confidence=0.9, has_content_hash=True, has_lineage=True),
    ],
)

with container.session() as session:
    svc = container.build(session)
    assessment = svc.scoring.score(scoring_input)
    print(assessment.trust_score.value, assessment.confidence_level)
```

## Pure compute (no persistence)

```python
from trust_scoring.services.trust_scoring_service import TrustScoringService
from trust_scoring.interfaces.trust_repository import TrustRepository

# Inject a stub / fake TrustRepository, or call compute() after wiring DI.
# assessment = TrustScoringService(repo).compute(scoring_input)
```

## Layout

```
trust_scoring/
  domain/         # models, inputs, weights, history, enums
  interfaces/     # Trust / Confidence / History repository ports
  persistence/    # SQLAlchemy ORM + Postgres repos
  services/       # scoring / evidence / cross-val / history / correlation / aggregation
  query/          # filters + pagination
  di/             # composition root
```

## Scoring inputs

Assembled by callers from:

- Evidence Repository
- Asset Inventory
- Threat Intelligence
- Scanner metadata
- Finding history
- Correlation results

## Scoring outputs

- Overall Trust Score (0–100)
- Confidence Level (Very High → Very Low)
- Supporting / Negative Factors
- Confidence Explanation
- Recommendation Confidence (act / investigate / defer / discard)

## Architecture doc

See ``docs/architecture/12-trust-scoring-engine.md``.
"""
