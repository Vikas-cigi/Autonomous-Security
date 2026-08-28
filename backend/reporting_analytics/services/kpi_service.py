"""Deterministic KPI aggregation from platform snapshots (no risk/trust recalculation)."""

from __future__ import annotations

from typing import List

from reporting_analytics.domain.enums import KPIName, TrendDirection
from reporting_analytics.domain.inputs import PlatformAnalyticsInput
from reporting_analytics.domain.models import KPI


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def _trend(current: float, previous: float | None) -> TrendDirection:
    if previous is None:
        return TrendDirection.UNKNOWN
    delta = current - previous
    if abs(delta) < 1e-9:
        return TrendDirection.FLAT
    return TrendDirection.UP if delta > 0 else TrendDirection.DOWN


class KPIService:
    """Compute KPIs strictly from caller-provided snapshot counts/rates."""

    def compute(self, snapshot: PlatformAnalyticsInput) -> List[KPI]:
        f = snapshot.findings
        a = snapshot.assets
        ex = snapshot.executions
        v = snapshot.verifications
        ap = snapshot.approvals
        rem = snapshot.remediation
        risk = snapshot.risk
        trust = snapshot.trust
        sla = snapshot.sla
        ai = snapshot.ai_usage
        comp = snapshot.compliance

        coverage = _rate(a.covered_assets, a.total_assets)
        exec_success = _rate(ex.success_count, ex.total_executions)
        ver_success = _rate(v.verified_count, v.total_verifications)
        auto_approval = _rate(ap.auto_approved_count, ap.total_approvals)
        rollback = _rate(ex.rollback_count, ex.total_executions)
        sla_ratio = _rate(sla.within_sla_count, sla.within_sla_count + sla.breached_count)

        risk_reduction = 0.0
        if (
            risk.pre_period_average_risk is not None
            and risk.post_period_average_risk is not None
            and risk.pre_period_average_risk > 0
        ):
            risk_reduction = max(
                0.0,
                min(
                    1.0,
                    (risk.pre_period_average_risk - risk.post_period_average_risk)
                    / risk.pre_period_average_risk,
                ),
            )

        utilization = min(
            1.0,
            (
                ex.total_executions
                + v.total_verifications
                + ap.total_approvals
                + snapshot.decisions.total_decisions
            )
            / 100.0,
        )

        return [
            KPI(
                name=KPIName.TOTAL_FINDINGS,
                label="Total Findings",
                value=float(f.total),
                unit="count",
            ),
            KPI(
                name=KPIName.OPEN_FINDINGS,
                label="Open Findings",
                value=float(f.open),
                unit="count",
            ),
            KPI(
                name=KPIName.CLOSED_FINDINGS,
                label="Closed Findings",
                value=float(f.closed),
                unit="count",
            ),
            KPI(
                name=KPIName.MTTR_HOURS,
                label="Mean Time To Remediate",
                value=rem.mean_time_to_remediate_hours,
                unit="hours",
            ),
            KPI(
                name=KPIName.MTTD_HOURS,
                label="Mean Time To Detect",
                value=rem.mean_time_to_detect_hours,
                unit="hours",
            ),
            KPI(
                name=KPIName.APPROVAL_TIME_HOURS,
                label="Approval Time",
                value=ap.mean_approval_time_hours,
                unit="hours",
            ),
            KPI(
                name=KPIName.EXECUTION_SUCCESS_RATE,
                label="Execution Success Rate",
                value=exec_success,
                unit="ratio",
            ),
            KPI(
                name=KPIName.VERIFICATION_SUCCESS_RATE,
                label="Verification Success Rate",
                value=ver_success,
                unit="ratio",
            ),
            KPI(
                name=KPIName.AUTO_APPROVAL_RATE,
                label="Auto Approval Rate",
                value=auto_approval,
                unit="ratio",
            ),
            KPI(
                name=KPIName.ROLLBACK_RATE,
                label="Rollback Rate",
                value=rollback,
                unit="ratio",
            ),
            KPI(
                name=KPIName.COMPLIANCE_SCORE,
                label="Compliance Score",
                value=comp.compliance_score,
                unit="score",
            ),
            KPI(
                name=KPIName.RISK_REDUCTION,
                label="Risk Reduction",
                value=risk_reduction,
                unit="ratio",
                trend=_trend(
                    risk.post_period_average_risk or risk.average_risk,
                    risk.pre_period_average_risk,
                ),
            ),
            KPI(
                name=KPIName.TRUST_DISTRIBUTION,
                label="Average Trust",
                value=trust.average_trust,
                unit="score",
                metadata={
                    "low": str(trust.low_trust_count),
                    "medium": str(trust.medium_trust_count),
                    "high": str(trust.high_trust_count),
                },
            ),
            KPI(
                name=KPIName.ASSET_COVERAGE,
                label="Asset Coverage",
                value=coverage,
                unit="ratio",
            ),
            KPI(
                name=KPIName.VULNERABILITY_TREND,
                label="Open Critical+High",
                value=float(f.critical + f.high),
                unit="count",
            ),
            KPI(
                name=KPIName.SLA_COMPLIANCE,
                label="SLA Compliance",
                value=sla_ratio,
                unit="ratio",
            ),
            KPI(
                name=KPIName.AI_USAGE,
                label="AI Invocations",
                value=float(ai.total_invocations),
                unit="count",
                metadata={"tokens": str(ai.total_tokens)},
            ),
            KPI(
                name=KPIName.PLATFORM_UTILIZATION,
                label="Platform Utilization",
                value=utilization,
                unit="ratio",
            ),
            KPI(
                name=KPIName.MULTI_TENANT_METRICS,
                label="Tenant Activity Volume",
                value=float(
                    f.total
                    + ex.total_executions
                    + v.total_verifications
                    + snapshot.assets.total_assets
                ),
                unit="count",
            ),
        ]
