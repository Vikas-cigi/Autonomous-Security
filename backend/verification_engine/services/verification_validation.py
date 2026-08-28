"""Structural validation for Verification Engine inputs."""

from __future__ import annotations

from verification_engine.domain.inputs import VerificationRequest
from verification_engine.domain.models import VerificationResult
from verification_engine.domain.enums import VerificationStatus
from verification_engine.exceptions import (
    InvalidVerificationRequestError,
    VerificationStateError,
)


class VerificationValidationService:
    """Validate requests and state transitions. Does not execute remediation."""

    def validate_request(self, request: VerificationRequest) -> None:
        errors: list[str] = []

        if request.decision.tenant_id is None:
            errors.append("decision.tenant_id is required")
        if request.decision.finding_id != request.finding.finding_id:
            errors.append("decision.finding_id must match finding.finding_id")
        if request.execution.failed_step_count < 0:
            errors.append("execution.failed_step_count must be >= 0")
        if request.execution.succeeded_step_count < 0:
            errors.append("execution.succeeded_step_count must be >= 0")
        if request.org_policy.min_risk_reduction_ratio < 0:
            errors.append("org_policy.min_risk_reduction_ratio must be >= 0")
        if request.org_policy.require_rescan and request.rescan.performed is False:
            # Allowed at request time — check will fail later if still missing.
            pass
        if request.risk is not None and request.risk.post_risk_score is not None:
            if request.risk.post_risk_score > request.risk.pre_risk_score + 1e-9:
                # Not an input error — risk increase is a verification signal.
                pass

        if errors:
            raise InvalidVerificationRequestError(
                "Invalid verification request",
                details={"errors": errors},
            )

    def ensure_runnable(self, result: VerificationResult) -> None:
        if result.status not in {
            VerificationStatus.PENDING,
            VerificationStatus.RUNNING,
        }:
            raise VerificationStateError(
                f"Cannot run verification in status {result.status.value}",
                details={
                    "verification_id": str(result.id),
                    "status": result.status.value,
                },
            )

    def ensure_cancellable(self, result: VerificationResult) -> None:
        if result.is_terminal:
            raise VerificationStateError(
                f"Cannot cancel verification in terminal status {result.status.value}",
                details={
                    "verification_id": str(result.id),
                    "status": result.status.value,
                },
            )
