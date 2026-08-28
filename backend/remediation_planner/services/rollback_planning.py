"""RollbackPlanningService — compensating rollback steps."""

from __future__ import annotations

from typing import List

from remediation_planner.domain.enums import ExecutionType, StepKind
from remediation_planner.domain.models import RemediationStep, RollbackPlan


class RollbackPlanningService:
    """Build a deterministic rollback plan from forward remediation steps."""

    def build(
        self,
        forward_steps: List[RemediationStep],
        execution_type: ExecutionType,
        *,
        target: str,
    ) -> RollbackPlan:
        destructive = [
            s
            for s in sorted(forward_steps, key=lambda x: x.sequence)
            if s.is_destructive
        ]
        rollback_steps: List[RemediationStep] = []
        seq = 1
        for step in reversed(destructive):
            rollback_steps.append(
                RemediationStep(
                    sequence=seq,
                    kind=StepKind.ROLLBACK,
                    execution_type=execution_type,
                    action=f"Rollback: undo '{step.action}'",
                    target=step.target or target,
                    description=(
                        f"Compensate destructive step seq={step.sequence} "
                        f"({step.action})."
                    ),
                    timeout_seconds=step.timeout_seconds,
                    estimated_duration_seconds=max(60, step.estimated_duration_seconds // 2),
                    is_destructive=True,
                    parameters={"rolls_back_step_id": str(step.id)},
                )
            )
            seq += 1

        if not rollback_steps:
            rollback_steps.append(
                RemediationStep(
                    sequence=1,
                    kind=StepKind.ROLLBACK,
                    execution_type=execution_type,
                    action="No-op rollback (no destructive forward steps)",
                    target=target,
                    description="Plan has no destructive steps; record audit only.",
                    timeout_seconds=60,
                    estimated_duration_seconds=60,
                    is_destructive=False,
                )
            )

        automatic = execution_type in {
            ExecutionType.CONFIGURATION_CHANGE,
            ExecutionType.FIREWALL_UPDATE,
        } and all(not s.requires_approval for s in destructive)

        return RollbackPlan(
            summary=(
                f"Rollback strategy for {execution_type.value} with "
                f"{len(rollback_steps)} compensating step(s)."
            ),
            steps=rollback_steps,
            automatic=automatic,
            trigger_conditions=[
                "forward_step_failed",
                "validation_check_failed",
                "operator_abort",
            ],
        )
