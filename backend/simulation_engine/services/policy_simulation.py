"""Policy conflict detection for dry-run remediation simulation."""

from __future__ import annotations

from typing import List

from simulation_engine.domain.inputs import SimulationRequest
from simulation_engine.domain.models import (
    DowntimeEstimate,
    PolicyImpact,
    RollbackAssessment,
)


class PolicySimulationService:
    """Detect policy violations and conflicts without calling Policy Engine APIs."""

    def evaluate(
        self,
        request: SimulationRequest,
        *,
        downtime: DowntimeEstimate,
        rollback: RollbackAssessment,
    ) -> PolicyImpact:
        policy = request.policy
        plan = request.plan
        asset = request.asset
        violations: List[str] = []
        conflicts: List[str] = []

        if plan.execution_type in policy.blocked_execution_types:
            violations.append(
                f"Execution type '{plan.execution_type}' is blocked by policy."
            )

        env = (asset.environment or "").lower() if asset else ""
        destructive = any(s.is_destructive for s in plan.steps)
        if (
            policy.deny_destructive_in_production
            and destructive
            and env in {"production", "prod"}
        ):
            violations.append(
                "Destructive remediation denied in production by policy."
            )

        if policy.deny_without_rollback and not rollback.rollback_possible:
            violations.append("Policy requires rollback; simulation found gaps.")

        if (
            policy.max_downtime_seconds is not None
            and downtime.seconds > policy.max_downtime_seconds
        ):
            violations.append(
                f"Estimated downtime {downtime.seconds}s exceeds policy max "
                f"{policy.max_downtime_seconds}s."
            )

        if policy.require_change_window and not plan.change_window_required:
            conflicts.append(
                "Policy requires a change window but plan does not mark one as required."
            )

        if policy.require_approval and not plan.approval_required:
            conflicts.append(
                "Policy requires approval but plan marks approval as not required."
            )

        if policy.require_simulation is False:
            conflicts.append(
                "Policy marks simulation optional; proceeding with dry-run anyway."
            )

        requires_approval = policy.require_approval or plan.approval_required
        requires_window = (
            policy.require_change_window
            or plan.change_window_required
            or downtime.maintenance_window_recommended
        )

        if violations:
            explanation = f"{len(violations)} policy violation(s) detected."
        elif conflicts:
            explanation = f"{len(conflicts)} policy conflict(s) require review."
        else:
            explanation = "No policy violations; constraints satisfied."

        return PolicyImpact(
            policy_version=policy.policy_version,
            violations=violations,
            conflicts=conflicts,
            requires_approval=requires_approval,
            requires_change_window=requires_window,
            explanation=explanation,
        )
