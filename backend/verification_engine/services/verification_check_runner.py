"""Deterministic verification checks — no remediation, risk calc, or AI."""

from __future__ import annotations

from typing import List, Optional

from models.common import new_id
from verification_engine.domain.enums import CheckResultStatus, CheckType
from verification_engine.domain.inputs import VerificationRequest
from verification_engine.domain.models import (
    VerificationCheck,
    VerificationComparison,
    VerificationEvidence,
    VerificationPlan,
)


class VerificationCheckRunner:
    """Execute the planned verification checks against snapshots."""

    def run_all(
        self,
        *,
        request: VerificationRequest,
        plan: VerificationPlan,
        evidence: List[VerificationEvidence],
        comparison: VerificationComparison,
    ) -> List[VerificationCheck]:
        results: List[VerificationCheck] = []
        for check_type in plan.checks:
            results.append(
                self.run_one(
                    check_type=check_type,
                    request=request,
                    plan=plan,
                    evidence=evidence,
                    comparison=comparison,
                )
            )
        return results

    def run_one(
        self,
        *,
        check_type: CheckType,
        request: VerificationRequest,
        plan: VerificationPlan,
        evidence: List[VerificationEvidence],
        comparison: VerificationComparison,
    ) -> VerificationCheck:
        handlers = {
            CheckType.REMEDIATION_COMPLETED: self._remediation_completed,
            CheckType.FINDING_RESOLVED: self._finding_resolved,
            CheckType.CONFIGURATION_VALIDATED: self._configuration_validated,
            CheckType.SERVICE_AVAILABILITY: self._service_availability,
            CheckType.COMPLIANCE_VERIFIED: self._compliance_verified,
            CheckType.POLICY_COMPLIANCE: self._policy_compliance,
            CheckType.ROLLBACK_VERIFICATION: self._rollback_verification,
            CheckType.INFRASTRUCTURE_VALIDATION: self._infrastructure_validation,
            CheckType.RISK_REDUCTION: self._risk_reduction,
            CheckType.RESCAN: self._rescan,
        }
        handler = handlers.get(check_type)
        if handler is None:
            return VerificationCheck(
                check_id=new_id(),
                check_type=check_type,
                name=check_type.value,
                status=CheckResultStatus.SKIPPED,
                passed=False,
                details=f"Unknown check type {check_type.value}",
            )
        return handler(request=request, plan=plan, evidence=evidence, comparison=comparison)

    def _remediation_completed(self, **kw) -> VerificationCheck:
        request: VerificationRequest = kw["request"]
        ex = request.execution
        passed = bool(ex.success) and ex.failed_step_count == 0 and not ex.rolled_back
        details = (
            f"Execution status={ex.execution_status}, success={ex.success}, "
            f"failed_steps={ex.failed_step_count}, rolled_back={ex.rolled_back}."
        )
        return self._check(
            CheckType.REMEDIATION_COMPLETED,
            "Expected remediation completed",
            passed,
            details,
        )

    def _finding_resolved(self, **kw) -> VerificationCheck:
        request: VerificationRequest = kw["request"]
        comparison: VerificationComparison = kw["comparison"]
        evidence: List[VerificationEvidence] = kw["evidence"]

        if request.rescan.performed and request.rescan.finding_still_present is not None:
            passed = request.rescan.finding_still_present is False
            details = (
                f"Rescan finding_still_present={request.rescan.finding_still_present}."
            )
            return self._check(
                CheckType.FINDING_RESOLVED, "Security finding resolved", passed, details
            )

        post = [e for e in evidence if e.phase == "post"]
        if any(e.indicates_resolved is True for e in post) and not any(
            e.indicates_resolved is False for e in post
        ):
            return self._check(
                CheckType.FINDING_RESOLVED,
                "Security finding resolved",
                True,
                "Post-remediation evidence indicates finding resolved.",
            )
        if comparison.unresolved_signals > 0:
            return self._check(
                CheckType.FINDING_RESOLVED,
                "Security finding resolved",
                False,
                f"Unresolved post evidence signals={comparison.unresolved_signals}.",
            )
        if request.execution.success and comparison.resolved_signals > 0:
            return self._check(
                CheckType.FINDING_RESOLVED,
                "Security finding resolved",
                True,
                "Execution succeeded with positive resolution signals.",
            )
        return self._check(
            CheckType.FINDING_RESOLVED,
            "Security finding resolved",
            False,
            "Insufficient evidence to confirm finding resolution.",
            status=CheckResultStatus.INCONCLUSIVE,
        )

    def _configuration_validated(self, **kw) -> VerificationCheck:
        evidence: List[VerificationEvidence] = kw["evidence"]
        post = [e for e in evidence if e.phase == "post"]
        config = [
            e
            for e in post
            if e.kind in {"configuration", "config", "hardening"}
            or e.attributes.get("configuration_validated") == "true"
        ]
        if config:
            failed = [e for e in config if e.indicates_resolved is False]
            passed = not failed
            return self._check(
                CheckType.CONFIGURATION_VALIDATED,
                "Configuration validated",
                passed,
                f"Configuration evidence items={len(config)}, failed={len(failed)}.",
            )
        # Soft pass when execution succeeded and no contrary config evidence
        request: VerificationRequest = kw["request"]
        if request.execution.success:
            return self._check(
                CheckType.CONFIGURATION_VALIDATED,
                "Configuration validated",
                True,
                "No contrary configuration evidence; execution succeeded.",
            )
        return self._check(
            CheckType.CONFIGURATION_VALIDATED,
            "Configuration validated",
            False,
            "No configuration evidence and execution did not succeed.",
        )

    def _service_availability(self, **kw) -> VerificationCheck:
        request: VerificationRequest = kw["request"]
        evidence: List[VerificationEvidence] = kw["evidence"]
        if request.asset is None:
            return self._check(
                CheckType.SERVICE_AVAILABILITY,
                "Service availability confirmed",
                True,
                "No asset snapshot; service check skipped as soft pass.",
                status=CheckResultStatus.SKIPPED,
            )
        down = [
            e
            for e in evidence
            if e.phase == "post"
            and (
                e.kind in {"availability", "service"}
                and e.indicates_resolved is False
                or e.attributes.get("service_up") == "false"
            )
        ]
        if down:
            return self._check(
                CheckType.SERVICE_AVAILABILITY,
                "Service availability confirmed",
                False,
                f"Service availability failures reported ({len(down)}).",
            )
        expected = request.asset.service_expected_up
        return self._check(
            CheckType.SERVICE_AVAILABILITY,
            "Service availability confirmed",
            expected,
            f"Asset service_expected_up={expected}; no contrary evidence.",
        )

    def _compliance_verified(self, **kw) -> VerificationCheck:
        request: VerificationRequest = kw["request"]
        evidence: List[VerificationEvidence] = kw["evidence"]
        plan: VerificationPlan = kw["plan"]
        if not plan.require_compliance:
            return self._check(
                CheckType.COMPLIANCE_VERIFIED,
                "Compliance verified",
                True,
                "Compliance check not required by plan.",
                status=CheckResultStatus.SKIPPED,
            )
        tags = request.asset.compliance_tags if request.asset else []
        compliance_ev = [
            e
            for e in evidence
            if e.phase == "post"
            and (
                e.kind in {"compliance", "policy"}
                or e.attributes.get("compliance") == "true"
            )
        ]
        if compliance_ev:
            failed = [e for e in compliance_ev if e.indicates_resolved is False]
            return self._check(
                CheckType.COMPLIANCE_VERIFIED,
                "Compliance verified",
                not failed,
                f"Compliance evidence={len(compliance_ev)}, failed={len(failed)}.",
            )
        if tags:
            return self._check(
                CheckType.COMPLIANCE_VERIFIED,
                "Compliance verified",
                True,
                f"Asset compliance tags present ({len(tags)}); no contrary evidence.",
            )
        return self._check(
            CheckType.COMPLIANCE_VERIFIED,
            "Compliance verified",
            False,
            "Compliance required but no compliance evidence or tags available.",
            status=CheckResultStatus.INCONCLUSIVE,
        )

    def _policy_compliance(self, **kw) -> VerificationCheck:
        request: VerificationRequest = kw["request"]
        plan: VerificationPlan = kw["plan"]
        issues: list[str] = []
        if plan.require_rescan and not request.rescan.performed:
            issues.append("require_rescan but rescan not performed")
        if plan.require_compliance and request.asset is None:
            issues.append("require_compliance but asset snapshot missing")
        passed = len(issues) == 0
        details = (
            "Org policy requirements satisfied."
            if passed
            else "Policy gaps: " + "; ".join(issues)
        )
        return self._check(
            CheckType.POLICY_COMPLIANCE,
            "Policy compliance confirmed",
            passed,
            details,
        )

    def _rollback_verification(self, **kw) -> VerificationCheck:
        request: VerificationRequest = kw["request"]
        if not request.execution.rolled_back:
            return self._check(
                CheckType.ROLLBACK_VERIFICATION,
                "Rollback verification",
                True,
                "No rollback occurred.",
                status=CheckResultStatus.SKIPPED,
            )
        # Rollback means remediation did not stick — fail this check
        return self._check(
            CheckType.ROLLBACK_VERIFICATION,
            "Rollback verification",
            False,
            "Execution was rolled back; remediation not sustained.",
        )

    def _infrastructure_validation(self, **kw) -> VerificationCheck:
        request: VerificationRequest = kw["request"]
        evidence: List[VerificationEvidence] = kw["evidence"]
        infra = [
            e
            for e in evidence
            if e.phase == "post"
            and e.kind in {"infrastructure", "host", "network"}
        ]
        if infra:
            failed = [e for e in infra if e.indicates_resolved is False]
            return self._check(
                CheckType.INFRASTRUCTURE_VALIDATION,
                "Infrastructure validation",
                not failed,
                f"Infrastructure evidence={len(infra)}, failed={len(failed)}.",
            )
        if request.asset is not None or request.execution.success:
            return self._check(
                CheckType.INFRASTRUCTURE_VALIDATION,
                "Infrastructure validation",
                True,
                "Asset present or execution succeeded; no contrary infra evidence.",
            )
        return self._check(
            CheckType.INFRASTRUCTURE_VALIDATION,
            "Infrastructure validation",
            False,
            "No infrastructure evidence and execution did not succeed.",
        )

    def _risk_reduction(self, **kw) -> VerificationCheck:
        request: VerificationRequest = kw["request"]
        comparison: VerificationComparison = kw["comparison"]
        if request.risk is None:
            return self._check(
                CheckType.RISK_REDUCTION,
                "Risk reduction confirmation",
                True,
                "No risk snapshot provided; check skipped.",
                status=CheckResultStatus.SKIPPED,
            )
        if comparison.post_risk_score is None or comparison.risk_reduction_ratio is None:
            return self._check(
                CheckType.RISK_REDUCTION,
                "Risk reduction confirmation",
                False,
                "Post-risk score missing; cannot confirm reduction.",
                status=CheckResultStatus.INCONCLUSIVE,
            )
        required = request.org_policy.min_risk_reduction_ratio
        passed = comparison.risk_reduction_ratio >= required
        return self._check(
            CheckType.RISK_REDUCTION,
            "Risk reduction confirmation",
            passed,
            (
                f"Risk reduction_ratio={comparison.risk_reduction_ratio:.3f} "
                f"(required>={required:.3f}); "
                f"{comparison.pre_risk_score} → {comparison.post_risk_score}."
            ),
        )

    def _rescan(self, **kw) -> VerificationCheck:
        request: VerificationRequest = kw["request"]
        plan: VerificationPlan = kw["plan"]
        if not plan.require_rescan and not request.rescan.performed:
            return self._check(
                CheckType.RESCAN,
                "Automated rescan",
                True,
                "Rescan not required.",
                status=CheckResultStatus.SKIPPED,
            )
        if not request.rescan.performed:
            return self._check(
                CheckType.RESCAN,
                "Automated rescan",
                False,
                "Rescan required but not performed by caller.",
            )
        still = request.rescan.finding_still_present
        if still is True:
            return self._check(
                CheckType.RESCAN,
                "Automated rescan",
                False,
                request.rescan.summary or "Rescan still detected finding.",
            )
        if still is False:
            return self._check(
                CheckType.RESCAN,
                "Automated rescan",
                True,
                request.rescan.summary or "Rescan confirms finding cleared.",
            )
        return self._check(
            CheckType.RESCAN,
            "Automated rescan",
            True,
            request.rescan.summary or "Rescan performed; finding presence unknown.",
            status=CheckResultStatus.INCONCLUSIVE,
        )

    @staticmethod
    def _check(
        check_type: CheckType,
        name: str,
        passed: bool,
        details: str,
        *,
        status: Optional[CheckResultStatus] = None,
        evidence_ids: Optional[list] = None,
    ) -> VerificationCheck:
        if status is None:
            status = CheckResultStatus.PASSED if passed else CheckResultStatus.FAILED
        # Inconclusive still carries passed=False for gating unless explicitly passed
        effective_passed = passed if status != CheckResultStatus.SKIPPED else True
        if status == CheckResultStatus.INCONCLUSIVE:
            effective_passed = False
        return VerificationCheck(
            check_id=new_id(),
            check_type=check_type,
            name=name,
            status=status,
            passed=effective_passed if status != CheckResultStatus.SKIPPED else True,
            details=details,
            evidence_ids=list(evidence_ids or []),
        )
