"""Rollback validation for dry-run remediation simulation."""

from __future__ import annotations

from typing import List

from simulation_engine.domain.inputs import SimulationRequest
from simulation_engine.domain.models import RollbackAssessment


class RollbackAnalysisService:
    """Validate rollback coverage without executing rollback steps."""

    def assess(self, request: SimulationRequest) -> RollbackAssessment:
        plan = request.plan
        gaps: List[str] = []

        forward = list(plan.steps)
        rollback = list(plan.rollback_steps)
        destructive_forward = [s for s in forward if s.is_destructive]

        if not rollback and any(
            s.execution_type
            not in {"manual_investigation", "monitor", "observe", "policy_exception"}
            for s in forward
        ):
            gaps.append("No rollback steps declared for a mutating plan.")

        if destructive_forward and not rollback:
            gaps.append("Destructive steps present without rollback coverage.")

        if plan.rollback_automatic and not rollback:
            gaps.append("Automatic rollback requested but no rollback steps exist.")

        # Coverage heuristic: at least one rollback per destructive step, or 1:1 count
        if destructive_forward and rollback:
            if len(rollback) < len(destructive_forward):
                gaps.append(
                    f"Rollback steps ({len(rollback)}) fewer than destructive "
                    f"forward steps ({len(destructive_forward)})."
                )

        estimated = sum(s.estimated_duration_seconds for s in rollback)
        possible = len(gaps) == 0 and (
            bool(rollback)
            or all(
                s.execution_type
                in {"manual_investigation", "monitor", "observe", "policy_exception"}
                for s in forward
            )
        )

        if possible and rollback:
            explanation = (
                f"Rollback feasible with {len(rollback)} step(s); "
                f"estimated rollback duration {estimated}s."
            )
        elif possible:
            explanation = "Non-mutating plan; rollback not required."
        else:
            explanation = "Rollback gaps detected: " + "; ".join(gaps)

        return RollbackAssessment(
            rollback_possible=possible,
            automatic_rollback=bool(plan.rollback_automatic and possible and rollback),
            rollback_step_count=len(rollback),
            estimated_rollback_seconds=estimated,
            gaps=gaps,
            explanation=explanation,
        )
