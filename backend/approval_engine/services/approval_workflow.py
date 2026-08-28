"""Build and advance multi-stage approval workflows."""

from __future__ import annotations

from typing import List, Optional

from models.common import new_id, utc_now

from approval_engine.domain.enums import (
    ApprovalMode,
    ApprovalState,
    ApprovalType,
    ApproverRole,
    AssignmentStatus,
    StageStatus,
)
from approval_engine.domain.inputs import ApprovalSubmitRequest
from approval_engine.domain.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStage,
    ApprovalWorkflow,
    ExecutionAuthorization,
)
from approval_engine.exceptions import ApprovalStateError
from approval_engine.services.approval_policy import PolicyEvaluationResult
from approval_engine.services.approval_routing import ApprovalRoutingService


_ROLE_TO_TYPE: dict[ApproverRole, ApprovalType] = {
    ApproverRole.SECURITY_MANAGER: ApprovalType.SECURITY_REVIEW,
    ApproverRole.SECURITY_APPROVER: ApprovalType.SECURITY_REVIEW,
    ApproverRole.INFRASTRUCTURE_MANAGER: ApprovalType.INFRASTRUCTURE_REVIEW,
    ApproverRole.NETWORK_TEAM: ApprovalType.INFRASTRUCTURE_REVIEW,
    ApproverRole.OPERATIONS_MANAGER: ApprovalType.OPERATIONS_REVIEW,
    ApproverRole.CHANGE_MANAGER: ApprovalType.OPERATIONS_REVIEW,
    ApproverRole.COMPLIANCE_OFFICER: ApprovalType.COMPLIANCE_REVIEW,
    ApproverRole.EMERGENCY_APPROVER: ApprovalType.EMERGENCY_CHANGE,
    ApproverRole.BUSINESS_OWNER: ApprovalType.OPERATIONS_REVIEW,
    ApproverRole.DELEGATE: ApprovalType.OPERATIONS_REVIEW,
}


class ApprovalWorkflowService:
    """Create sequential/parallel workflows and record stage decisions."""

    def __init__(
        self,
        routing: Optional[ApprovalRoutingService] = None,
    ) -> None:
        self._routing = routing or ApprovalRoutingService()

    def build_workflow(
        self,
        approval_id,
        request: ApprovalSubmitRequest,
        evaluation: PolicyEvaluationResult,
    ) -> ApprovalWorkflow:
        stages: List[ApprovalStage] = []
        for idx, role in enumerate(evaluation.required_roles, start=1):
            approval_type = (
                evaluation.approval_types[idx - 1]
                if idx - 1 < len(evaluation.approval_types)
                else _ROLE_TO_TYPE.get(role, ApprovalType.OPERATIONS_REVIEW)
            )
            stage = ApprovalStage(
                id=new_id(),
                sequence=idx,
                name=f"{approval_type.value} ({role.value})",
                approval_type=approval_type,
                required_role=role,
                status=StageStatus.PENDING,
                mode_hint=evaluation.mode,
            )
            stage = self._routing.assign_stage(stage, request)
            if evaluation.mode == ApprovalMode.PARALLEL or idx == 1:
                stage.status = StageStatus.IN_PROGRESS
            stages.append(stage)

        return ApprovalWorkflow(
            id=new_id(),
            approval_id=approval_id,
            mode=evaluation.mode,
            stages=stages,
            current_stage_sequence=1 if stages else 1,
            escalated=False,
        )

    def apply_stage_decision(
        self,
        approval: ApprovalRequest,
        *,
        approve: bool,
        approver: str,
        stage_id=None,
        comment: Optional[str] = None,
    ) -> ApprovalRequest:
        if approval.is_terminal:
            raise ApprovalStateError(
                f"Cannot decide approval in terminal state {approval.state.value}"
            )

        workflow = approval.workflow
        stage = self._find_stage(workflow, stage_id)
        if stage.status not in {StageStatus.PENDING, StageStatus.IN_PROGRESS, StageStatus.ESCALATED}:
            raise ApprovalStateError(
                f"Stage {stage.sequence} is not actionable ({stage.status.value})"
            )

        now = utc_now()
        if approve:
            stage.status = StageStatus.APPROVED
            stage.decided_by = approver
            stage.decided_at = now
            stage.comment = comment
            for a in stage.assignments:
                if a.approver == approver or a.status == AssignmentStatus.PENDING:
                    a.status = AssignmentStatus.COMPLETED
                    a.completed_at = now
        else:
            stage.status = StageStatus.REJECTED
            stage.decided_by = approver
            stage.decided_at = now
            stage.comment = comment
            approval.state = ApprovalState.REJECTED
            approval.decision = ApprovalDecision(
                approval_id=approval.id,
                state=ApprovalState.REJECTED,
                decided_by=approver,
                decided_at=now,
                comment=comment,
                auto=False,
                execution_authorization=ExecutionAuthorization(
                    authorized=False,
                    approval_id=approval.id,
                    tenant_id=approval.tenant_id,
                    plan_id=approval.plan_id,
                    simulation_id=approval.simulation_id,
                    reason="Approval rejected",
                ),
            )
            approval.timeline.decided_at = now
            return approval

        # Advance workflow
        if workflow.mode == ApprovalMode.SEQUENTIAL:
            self._advance_sequential(workflow)
        else:
            # parallel: wait until all approved
            for s in workflow.stages:
                if s.status == StageStatus.PENDING:
                    s.status = StageStatus.IN_PROGRESS

        if workflow.all_stages_approved:
            approval.state = ApprovalState.APPROVED
            auth = ExecutionAuthorization(
                authorized=True,
                approval_id=approval.id,
                tenant_id=approval.tenant_id,
                plan_id=approval.plan_id,
                simulation_id=approval.simulation_id,
                issued_at=now,
                expires_at=approval.timeline.expires_at,
                reason="All approval stages completed",
            )
            approval.decision = ApprovalDecision(
                approval_id=approval.id,
                state=ApprovalState.APPROVED,
                decided_by=approver,
                decided_at=now,
                comment=comment,
                auto=False,
                execution_authorization=auth,
            )
            approval.timeline.decided_at = now
        else:
            active = next(
                (s for s in workflow.stages if s.status == StageStatus.IN_PROGRESS),
                None,
            )
            if active:
                workflow.current_stage_sequence = active.sequence

        approval.workflow = workflow
        return approval

    def _find_stage(self, workflow: ApprovalWorkflow, stage_id) -> ApprovalStage:
        if stage_id is not None:
            for s in workflow.stages:
                if s.id == stage_id:
                    return s
            raise ApprovalStateError(f"Stage {stage_id} not found")
        # Default: current in-progress or first pending
        for s in sorted(workflow.stages, key=lambda x: x.sequence):
            if s.status == StageStatus.IN_PROGRESS:
                return s
        for s in sorted(workflow.stages, key=lambda x: x.sequence):
            if s.status in {StageStatus.PENDING, StageStatus.ESCALATED}:
                return s
        raise ApprovalStateError("No actionable approval stage")

    def _advance_sequential(self, workflow: ApprovalWorkflow) -> None:
        stages = sorted(workflow.stages, key=lambda s: s.sequence)
        for i, stage in enumerate(stages):
            if stage.status == StageStatus.APPROVED:
                continue
            if stage.status in {StageStatus.PENDING, StageStatus.ESCALATED}:
                stage.status = StageStatus.IN_PROGRESS
                workflow.current_stage_sequence = stage.sequence
                # ensure later remain pending
                for later in stages[i + 1 :]:
                    if later.status == StageStatus.IN_PROGRESS:
                        later.status = StageStatus.PENDING
                return
            if stage.status == StageStatus.IN_PROGRESS:
                workflow.current_stage_sequence = stage.sequence
                return
