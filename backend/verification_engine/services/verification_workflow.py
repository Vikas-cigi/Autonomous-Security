"""Build deterministic verification plans and interpret outcomes."""

from __future__ import annotations

from verification_engine.domain.enums import (
    CheckResultStatus,
    CheckType,
    ClosureRecommendation,
    FindingDisposition,
    VerificationStatus,
)
from verification_engine.domain.inputs import VerificationRequest
from verification_engine.domain.models import VerificationCheck, VerificationPlan


class VerificationWorkflowService:
    """Plan which checks to run and map check results to lifecycle outcomes."""

    def build_plan(self, request: VerificationRequest) -> VerificationPlan:
        checks: list[CheckType] = [
            CheckType.REMEDIATION_COMPLETED,
            CheckType.FINDING_RESOLVED,
            CheckType.CONFIGURATION_VALIDATED,
            CheckType.INFRASTRUCTURE_VALIDATION,
        ]
        if request.org_policy.require_service_check:
            checks.append(CheckType.SERVICE_AVAILABILITY)
        if request.org_policy.require_compliance_check:
            checks.append(CheckType.COMPLIANCE_VERIFIED)
        checks.append(CheckType.POLICY_COMPLIANCE)
        if request.execution.rolled_back:
            checks.append(CheckType.ROLLBACK_VERIFICATION)
        if request.risk is not None:
            checks.append(CheckType.RISK_REDUCTION)
        if request.org_policy.require_rescan or request.rescan.performed:
            checks.append(CheckType.RESCAN)

        # Deduplicate while preserving order
        seen: set[CheckType] = set()
        ordered: list[CheckType] = []
        for c in checks:
            if c not in seen:
                seen.add(c)
                ordered.append(c)

        return VerificationPlan(
            checks=ordered,
            require_rescan=request.org_policy.require_rescan,
            require_compliance=request.org_policy.require_compliance_check,
            require_service_check=request.org_policy.require_service_check,
        )

    def resolve_outcome(
        self,
        *,
        request: VerificationRequest,
        checks: list[VerificationCheck],
    ) -> tuple[VerificationStatus, ClosureRecommendation, FindingDisposition, str]:
        """
        Deterministically map check results to status + closure recommendation.
        """
        evaluated = [c for c in checks if c.status != CheckResultStatus.SKIPPED]
        failed = [c for c in evaluated if not c.passed]
        passed = [c for c in evaluated if c.passed]

        finding_check = next(
            (c for c in checks if c.check_type == CheckType.FINDING_RESOLVED), None
        )
        rollback_check = next(
            (c for c in checks if c.check_type == CheckType.ROLLBACK_VERIFICATION),
            None,
        )
        remediation_check = next(
            (c for c in checks if c.check_type == CheckType.REMEDIATION_COMPLETED),
            None,
        )

        if (
            request.execution.rolled_back
            and request.org_policy.escalate_on_rollback
            and rollback_check is not None
            and not rollback_check.passed
        ):
            return (
                VerificationStatus.ESCALATED,
                ClosureRecommendation.ESCALATE_FINDING,
                FindingDisposition.ESCALATE,
                "Execution rolled back; escalation required by org policy.",
            )

        if finding_check is not None and not finding_check.passed:
            return (
                VerificationStatus.REOPENED,
                ClosureRecommendation.REOPEN_FINDING,
                FindingDisposition.REOPEN,
                "Finding not confirmed resolved; reopen recommended.",
            )

        if remediation_check is not None and not remediation_check.passed:
            return (
                VerificationStatus.FAILED,
                ClosureRecommendation.ADDITIONAL_REMEDIATION_REQUIRED,
                FindingDisposition.UNCHANGED,
                "Expected remediation was not completed successfully.",
            )

        if failed and passed:
            return (
                VerificationStatus.COMPLETED,
                ClosureRecommendation.MANUAL_INVESTIGATION,
                FindingDisposition.UNCHANGED,
                "Partial verification; manual investigation recommended.",
            )

        if failed and not passed:
            return (
                VerificationStatus.FAILED,
                ClosureRecommendation.ADDITIONAL_REMEDIATION_REQUIRED,
                FindingDisposition.UNCHANGED,
                "Verification checks failed.",
            )

        # All evaluated checks passed
        if request.org_policy.auto_close_on_verify:
            return (
                VerificationStatus.VERIFIED,
                ClosureRecommendation.CLOSE_FINDING,
                FindingDisposition.CLOSE,
                "All verification checks passed; close finding recommended.",
            )

        return (
            VerificationStatus.VERIFIED,
            ClosureRecommendation.MANUAL_INVESTIGATION,
            FindingDisposition.UNCHANGED,
            "Verification passed; auto-close disabled by policy.",
        )
