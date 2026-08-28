"""Validate execution inputs — authorization and structural checks only."""

from __future__ import annotations

from models.common import utc_now

from execution_engine.domain.inputs import ExecutionRequest
from execution_engine.exceptions import InvalidExecutionRequestError


class ExecutionValidationService:
    """
    Gate execution start.

    Does NOT evaluate Policy Engine rules, recalculate risk/trust, or call AI.
    Only validates authorization token + structural consistency.
    """

    APPROVED_STATES = {"approved", "auto_approved"}

    def validate_start(self, request: ExecutionRequest) -> None:
        auth = request.authorization
        if not auth.authorized:
            raise InvalidExecutionRequestError(
                "ExecutionAuthorization.authorized is false",
                details={"authorization_id": str(auth.authorization_id)},
            )

        if request.approval.state.lower() not in self.APPROVED_STATES:
            raise InvalidExecutionRequestError(
                f"Approval state '{request.approval.state}' is not executable",
                details={"approval_id": str(request.approval.approval_id)},
            )

        if auth.tenant_id != request.decision.tenant_id:
            raise InvalidExecutionRequestError(
                "Authorization tenant_id does not match decision tenant_id"
            )

        if auth.plan_id != request.plan.plan_id:
            raise InvalidExecutionRequestError(
                "Authorization plan_id does not match remediation plan"
            )

        if auth.approval_id != request.approval.approval_id:
            raise InvalidExecutionRequestError(
                "Authorization approval_id does not match approval decision"
            )

        now = request.evaluated_at or utc_now()
        if auth.expires_at is not None and now >= auth.expires_at:
            raise InvalidExecutionRequestError(
                "ExecutionAuthorization has expired",
                details={"expires_at": auth.expires_at.isoformat()},
            )

        if request.org_policy.require_simulation_safe and not request.simulation.safe_to_execute:
            raise InvalidExecutionRequestError(
                "Simulation is not safe_to_execute; refusing execution",
                details={"simulation_id": str(request.simulation.simulation_id)},
            )

        if not request.plan.steps:
            raise InvalidExecutionRequestError("Remediation plan has no steps")

        sequences = [s.sequence for s in request.plan.steps]
        if len(sequences) != len(set(sequences)):
            raise InvalidExecutionRequestError("Plan step sequences must be unique")

        known = set(sequences)
        for step in request.plan.steps:
            for dep in step.depends_on_sequences:
                if dep not in known:
                    raise InvalidExecutionRequestError(
                        f"Step {step.sequence} depends on missing sequence {dep}"
                    )
                if dep >= step.sequence:
                    raise InvalidExecutionRequestError(
                        f"Step {step.sequence} has invalid dependency on {dep}"
                    )

        if request.asset and request.decision.finding_id is None:
            raise InvalidExecutionRequestError("finding_id is required")
