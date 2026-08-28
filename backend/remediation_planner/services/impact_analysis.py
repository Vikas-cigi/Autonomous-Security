"""ImpactAnalysisService — estimated blast radius and risk reduction."""

from __future__ import annotations

from datetime import timedelta
from typing import List, Tuple

from models.common import utc_now
from models.enums import Priority
from remediation_planner.domain.enums import (
    ExecutionType,
    ImpactBlastRadius,
    PlanStatus,
)
from remediation_planner.domain.inputs import RemediationPlanRequest
from remediation_planner.domain.models import (
    ApprovalRequirement,
    ChangeWindow,
    EstimatedDuration,
    EstimatedImpact,
    RemediationStep,
)
from models.enums import ApprovalStatus


class ImpactAnalysisService:
    """Deterministic impact, duration, approval, and change-window analysis."""

    def analyze(
        self,
        request: RemediationPlanRequest,
        steps: List[RemediationStep],
        execution_type: ExecutionType,
    ) -> Tuple[EstimatedImpact, EstimatedDuration, ApprovalRequirement, ChangeWindow, PlanStatus]:
        impact = self._impact(request, execution_type)
        duration = self._duration(steps)
        approval = self._approval(request, steps, execution_type)
        window = self._change_window(request, duration, execution_type)
        status = (
            PlanStatus.AWAITING_APPROVAL
            if approval.required
            else PlanStatus.READY_FOR_SIMULATION
        )
        if request.policy.require_simulation:
            status = (
                PlanStatus.AWAITING_APPROVAL
                if approval.required
                else PlanStatus.READY_FOR_SIMULATION
            )
        return impact, duration, approval, window, status

    def _impact(
        self,
        request: RemediationPlanRequest,
        execution_type: ExecutionType,
    ) -> EstimatedImpact:
        asset_crit = request.asset.criticality if request.asset else 0.5
        env = (request.asset.environment or "").lower() if request.asset else ""
        internet = bool(request.asset and request.asset.internet_facing)

        if execution_type == ExecutionType.NETWORK_ISOLATION:
            blast = ImpactBlastRadius.ASSET
            downtime = 900 if internet else 300
        elif execution_type in {
            ExecutionType.SECRET_ROTATION,
            ExecutionType.CONTAINER_UPDATE,
            ExecutionType.PACKAGE_UPGRADE,
            ExecutionType.PATCH,
        }:
            blast = (
                ImpactBlastRadius.ENVIRONMENT
                if env in {"production", "prod"}
                else ImpactBlastRadius.ASSET
            )
            downtime = int(300 + 600 * asset_crit)
        elif execution_type == ExecutionType.MANUAL_INVESTIGATION:
            blast = ImpactBlastRadius.NONE
            downtime = 0
        else:
            blast = ImpactBlastRadius.ASSET
            downtime = int(120 + 240 * asset_crit)

        if request.policy.max_downtime_seconds is not None:
            downtime = min(downtime, request.policy.max_downtime_seconds)

        risk_score = request.risk.enterprise_risk_score / 100.0
        reduction = round(min(0.95, 0.35 + 0.50 * risk_score), 4)
        if execution_type == ExecutionType.MANUAL_INVESTIGATION:
            reduction = round(min(0.25, 0.10 + 0.10 * risk_score), 4)

        residual = round(max(0.05, 1.0 - reduction) * (0.4 + 0.4 * asset_crit), 4)
        notes = (
            f"Estimated blast_radius={blast.value}, downtime={downtime}s, "
            f"risk_reduction={reduction:.2f} for {execution_type.value}."
        )
        return EstimatedImpact(
            blast_radius=blast,
            affected_asset_count=1,
            downtime_seconds=downtime,
            risk_reduction_estimate=reduction,
            residual_operational_risk=residual,
            notes=notes,
        )

    def _duration(self, steps: List[RemediationStep]) -> EstimatedDuration:
        execution = sum(
            s.estimated_duration_seconds
            for s in steps
            if s.kind.value != "validation"
        )
        validation = sum(
            s.estimated_duration_seconds
            for s in steps
            if s.kind.value == "validation"
        )
        if execution <= 0:
            execution = sum(s.estimated_duration_seconds for s in steps)
        buffer = max(60, int(0.15 * (execution + validation)))
        total = execution + validation + buffer
        minutes = total // 60
        summary = f"~{minutes} minute(s) including validation buffer"
        return EstimatedDuration(
            execution_seconds=max(1, execution),
            validation_seconds=validation,
            buffer_seconds=buffer,
            total_seconds=total,
            human_summary=summary,
        )

    def _approval(
        self,
        request: RemediationPlanRequest,
        steps: List[RemediationStep],
        execution_type: ExecutionType,
    ) -> ApprovalRequirement:
        destructive = any(s.is_destructive for s in steps)
        high_priority = request.decision.priority in {Priority.P0, Priority.P1}
        required = (
            request.policy.require_approval
            or destructive
            or high_priority
            or execution_type
            in {
                ExecutionType.NETWORK_ISOLATION,
                ExecutionType.SECRET_ROTATION,
                ExecutionType.IAM_POLICY_CHANGE,
            }
        )
        dual = high_priority and destructive
        status = (
            ApprovalStatus.PENDING if required else ApprovalStatus.NOT_REQUIRED
        )
        roles = ["security_approver"]
        if dual:
            roles.append("change_manager")
        reason = (
            "Approval required due to destructive steps and/or high priority."
            if required
            else "No approval required for this low-impact plan."
        )
        return ApprovalRequirement(
            required=required,
            status=status,
            minimum_approvers=2 if dual else (1 if required else 0),
            dual_control=dual,
            roles=roles,
            reason=reason,
            designated_approver=request.decision.approver,
        )

    def _change_window(
        self,
        request: RemediationPlanRequest,
        duration: EstimatedDuration,
        execution_type: ExecutionType,
    ) -> ChangeWindow:
        prod = bool(
            request.asset
            and (request.asset.environment or "").lower() in {"production", "prod"}
        )
        required = (
            request.policy.require_change_window
            or (prod and execution_type != ExecutionType.MANUAL_INVESTIGATION)
            or duration.total_seconds >= 1800
        )
        start = None
        end = None
        if required:
            # Deterministic: recommend next UTC weekend maintenance slot from evaluated_at.
            base = request.evaluated_at or utc_now()
            # Move to next Saturday 02:00 UTC
            days_ahead = (5 - base.weekday()) % 7
            if days_ahead == 0 and (base.hour > 2 or (base.hour == 2 and base.minute > 0)):
                days_ahead = 7
            start = (base + timedelta(days=days_ahead)).replace(
                hour=2, minute=0, second=0, microsecond=0
            )
            end = start + timedelta(seconds=max(3600, duration.total_seconds))
        return ChangeWindow(
            required=required,
            preferred_start=start,
            preferred_end=end,
            timezone_name="UTC",
            rationale=(
                "Production or long-running change recommends a maintenance window."
                if required
                else "No dedicated change window required."
            ),
        )
