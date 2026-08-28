# Enterprise Verification Engine

Validates whether approved remediation actions were successfully executed and
whether original security findings have been resolved.

**Position in pipeline:** Execution Engine → **Verification Engine** → Reporting & Analytics

## Non-goals (hard constraints)

- Never executes remediation
- Never modifies remediation plans
- Never performs approval
- Never recalculates trust or risk (confirms reduction from caller snapshots only)
- Never invokes AI
- No REST APIs in this package

## Quick start

```python
from verification_engine import VerificationEngineContainer, VerificationRequest

container = VerificationEngineContainer.from_url(
    "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
    create_tables=True,
)

with container.session() as session:
    svc = container.build(session)
    result = svc.engine.verify(request)  # VerificationRequest snapshots
    print(result.status, result.closure_recommendation)
    canonical = result.to_canonical_verification_object()
```

## Package layout

```
verification_engine/
  domain/          # enums, inputs, models, history
  interfaces/      # repository ports
  persistence/     # SQLAlchemy ORM + Postgres repos (ve_*)
  services/        # validation, workflow, comparison, evidence, audit, reporting, facade
  query/           # filters + pagination
  di/              # VerificationEngineContainer
```

## Services

| Service | Role |
|---------|------|
| `VerificationEngineService` | Facade: verify / replay / cancel / search |
| `VerificationWorkflowService` | Build check plan + map outcomes |
| `VerificationValidationService` | Structural + state guards |
| `VerificationComparisonService` | Before/after evidence + risk snapshot compare |
| `VerificationEvidenceService` | Normalize pre/post/rescan evidence |
| `VerificationCheckRunner` | Deterministic verification checks |
| `VerificationReportingService` | Summary, report, metrics, finding disposition |
| `VerificationAuditService` | Audit trail |

## Outcomes

- Close Finding
- Reopen Finding
- Escalate Finding
- Manual Investigation
- Additional Remediation Required

## Persistence tables

- `ve_verifications`
- `ve_verification_versions`
- `ve_verification_audit`
- `ve_verification_evidence`
- `ve_audit_log`
