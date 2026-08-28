"""Validate approval inputs before workflow creation."""

from __future__ import annotations

from approval_engine.domain.inputs import ApprovalSubmitRequest
from approval_engine.exceptions import InvalidApprovalRequestError


class ApprovalValidationService:
    """
    Structural and governance pre-checks.

    Does not call AI, does not mutate plans/risk, does not execute remediation.
    """

    def validate_submit(self, request: ApprovalSubmitRequest) -> None:
        if not request.plan.summary.strip():
            raise InvalidApprovalRequestError("Plan summary is required")

        if request.org_policy.require_simulation_safe:
            if not request.simulation.safe_to_execute:
                raise InvalidApprovalRequestError(
                    "Simulation is not safe_to_execute; approval cannot proceed",
                    details={
                        "simulation_id": str(request.simulation.simulation_id),
                        "outcome": request.simulation.outcome,
                    },
                )
            if request.simulation.policy_violations:
                raise InvalidApprovalRequestError(
                    "Simulation has policy violations; approval blocked",
                    details={"violations": request.simulation.policy_violations},
                )

        if request.asset is None and request.plan.execution_type in {
            "firewall_change",
            "network_change",
            "security_group_change",
        }:
            raise InvalidApprovalRequestError(
                "Asset snapshot required for network/firewall remediations"
            )

        if request.emergency and not request.org_policy.emergency_bypass_roles:
            # Emergency still allowed; routing uses emergency approver role
            pass
