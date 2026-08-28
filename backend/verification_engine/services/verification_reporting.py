"""Build verification summaries, reports, and metrics."""

from __future__ import annotations

from typing import List

from models.common import utc_now
from verification_engine.domain.enums import (
    CheckResultStatus,
    ClosureRecommendation,
    FindingDisposition,
    VerificationStatus,
)
from verification_engine.domain.models import (
    VerificationCheck,
    VerificationComparison,
    VerificationFinding,
    VerificationMetrics,
    VerificationReport,
    VerificationResult,
    VerificationSummary,
)


class VerificationReportingService:
    def build_metrics(
        self,
        checks: List[VerificationCheck],
        *,
        duration_ms: int,
        evidence_compared: int,
    ) -> VerificationMetrics:
        return VerificationMetrics(
            total_checks=len(checks),
            passed_checks=sum(
                1
                for c in checks
                if c.passed and c.status != CheckResultStatus.SKIPPED
            ),
            failed_checks=sum(
                1
                for c in checks
                if not c.passed and c.status != CheckResultStatus.SKIPPED
            ),
            skipped_checks=sum(
                1 for c in checks if c.status == CheckResultStatus.SKIPPED
            ),
            duration_ms=max(0, duration_ms),
            evidence_compared=evidence_compared,
        )

    def build_summary(
        self,
        *,
        status: VerificationStatus,
        closure: ClosureRecommendation,
        rationale: str,
        checks: List[VerificationCheck],
    ) -> VerificationSummary:
        passed = sum(
            1 for c in checks if c.passed and c.status != CheckResultStatus.SKIPPED
        )
        failed = sum(
            1
            for c in checks
            if not c.passed and c.status != CheckResultStatus.SKIPPED
        )
        success = status == VerificationStatus.VERIFIED
        headline = f"Verification {status.value}: {closure.value}"
        details = (
            f"{rationale} Checks passed={passed}, failed={failed}. "
            f"Closure recommendation={closure.value}."
        )
        return VerificationSummary(
            headline=headline[:512],
            details=details[:8000],
            success=success,
            closure_recommendation=closure,
        )

    def build_finding(
        self,
        *,
        finding_id,
        prior_status: str,
        disposition: FindingDisposition,
        rationale: str,
    ) -> VerificationFinding:
        status_map = {
            FindingDisposition.CLOSE: "closed",
            FindingDisposition.REOPEN: "open",
            FindingDisposition.ESCALATE: "escalated",
            FindingDisposition.UNCHANGED: prior_status,
        }
        return VerificationFinding(
            finding_id=finding_id,
            prior_status=prior_status,
            disposition=disposition,
            recommended_status=status_map[disposition],
            rationale=rationale,
        )

    def build_report(self, result: VerificationResult) -> VerificationReport:
        if result.comparison is None:
            comparison = VerificationComparison(
                pre_evidence_count=0,
                post_evidence_count=0,
                explanation="No comparison available.",
            )
        else:
            comparison = result.comparison
        closure = (
            result.closure_recommendation
            or ClosureRecommendation.MANUAL_INVESTIGATION
        )
        disposition = (
            result.finding.disposition
            if result.finding
            else FindingDisposition.UNCHANGED
        )
        summary = (
            result.summary.details
            if result.summary
            else f"Verification status={result.status.value}"
        )
        return VerificationReport(
            verification_id=result.id,
            finding_id=result.finding_id,
            execution_id=result.execution_id,
            status=result.status,
            closure_recommendation=closure,
            finding_disposition=disposition,
            comparison=comparison,
            checks=list(result.checks),
            summary=summary,
            generated_at=utc_now(),
        )

    def attach_outputs(self, result: VerificationResult) -> VerificationResult:
        result.report = self.build_report(result)
        return result
