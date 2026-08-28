# Enterprise Reporting & Analytics Platform

Final Xolaris module for operational visibility, executive dashboards, compliance
reporting, remediation metrics, security posture analytics, AI operational
metrics, audit reporting, SLA tracking, and historical trends.

**Position:** Verification Engine → **Reporting & Analytics** (terminal)

## Hard constraints

- Never modifies platform source data
- Never executes remediation / approval
- Never invokes AI
- Never recalculates trust or risk (aggregates caller-provided snapshots only)
- No REST APIs in this package

## Quick start

```python
from reporting_analytics import (
    ReportingAnalyticsContainer,
    ReportGenerationRequest,
    PlatformAnalyticsInput,
    ReportType,
)

container = ReportingAnalyticsContainer.from_url(db_url, create_tables=True)
with container.session() as session:
    svc = container.build(session)
    report = svc.reporting.generate(
        ReportGenerationRequest(
            report_type=ReportType.EXECUTIVE.value,
            snapshot=PlatformAnalyticsInput(tenant_id=...),
        )
    )
    dash = svc.dashboard.build(...)
    export = svc.export.export(..., report=report)
```

## Package layout

```
reporting_analytics/
  domain/       # enums, inputs (snapshots), models, history
  interfaces/   # repository ports
  persistence/  # SQLAlchemy ORM + repos (ra_*)
  services/     # reporting, dashboard, KPI, trends, export, scheduling
  query/        # filters + pagination
  di/           # ReportingAnalyticsContainer
```

## Services

| Service | Role |
|---------|------|
| `ReportingService` | Generate all report types |
| `DashboardService` | RBAC-aware dashboards |
| `AnalyticsService` | Snapshot + KPI persistence |
| `KPIService` | Deterministic KPI aggregation |
| `TrendAnalysisService` | Historical / time-series trends |
| `ExportService` | JSON / CSV / Excel-TSV / PDF-text |
| `ReportSchedulingService` | Daily…Yearly / manual / event |

## Persistence tables

`ra_reports`, `ra_report_versions`, `ra_dashboards`, `ra_analytics_snapshots`,
`ra_kpis`, `ra_report_schedules`, `ra_exports`, `ra_reporting_audit`, `ra_audit_log`
