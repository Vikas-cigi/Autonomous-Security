"""ApprovalEngineService — facade governing remediation execution authorization."""

from __future__ import annotations

from datetime import timedelta
from typing import List, Optional
from uuid import UUID

from models.common import new_id, utc_now

from approval_engine.domain.enums import (
    ApprovalState,
    ApproverRole,
    AssignmentStatus,
    AuditAction,
    StageStatus,
)
from approval_engine.domain.inputs import (
    ApprovalSubmitRequest,
    DelegateApprovalRequest,
    EscalateApprovalRequest,
    RecordDecisionRequest,
)
from approval_engine.domain.models import (
    ALGORITHM_VERSION,
    ApprovalComment,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalTimeline,
    ExecutionAuthorization,
)
from approval_engine.exceptions import ApprovalStateError, InvalidApprovalRequestError
from approval_engine.interfaces.approval_repository import ApprovalRepository
from approval_engine.query.filters import ApprovalSearchFilter
from approval_engine.query.pagination import Page, PageRequest
from approval_engine.services.approval_audit import ApprovalAuditService
from approval_engine.services.approval_policy import ApprovalPolicyService
from approval_engine.services.approval_routing import ApprovalRoutingService
from approval_engine.services.approval_validation import ApprovalValidationService
from approval_engine.services.approval_workflow import ApprovalWorkflowService
from approval_engine.services.notification_preparation import (
    NotificationPreparationService,
)


class ApprovalEngineService:
    """
    Govern remediation execution authorization.

    Pipeline: after Simulation Engine, before Execution Engine.
    Never executes remediation. Never calls AI. Never mutates plans/risk.
    """

    def __init__(
        self,
        approval_repository: ApprovalRepository,
        *,
        policy_service: Optional[ApprovalPolicyService] = None,
        workflow_service: Optional[ApprovalWorkflowService] = None,
        routing_service: Optional[ApprovalRoutingService] = None,
        validation_service: Optional[ApprovalValidationService] = None,
        audit_service: Optional[ApprovalAuditService] = None,
        notification_service: Optional[NotificationPreparationService] = None,
        audit_logger: Optional[object] = None,
    ) -> None:
        self._repo = approval_repository
        self._policy = policy_service or ApprovalPolicyService()
        self._routing = routing_service or ApprovalRoutingService()
        self._workflow = workflow_service or ApprovalWorkflowService(
            routing=self._routing
        )
        self._validation = validation_service or ApprovalValidationService()
        self._audit = audit_service or ApprovalAuditService()
        self._notifications = notification_service or NotificationPreparationService()
        self._audit_logger = audit_logger

    def submit(
        self,
        request: ApprovalSubmitRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        approval_id: Optional[UUID] = None,
    ) -> ApprovalRequest:
        self._validation.validate_submit(request)
        result = self.compute(request, approval_id=approval_id)
        if persist:
            result = self._repo.save(
                result,
                actor=actor or request.actor or request.requester,
                change_summary="Approval request submitted",
            )
            self._audit.record(
                action=AuditAction.REQUEST_CREATED,
                message=result.summary,
                approval_id=result.id,
                plan_id=result.plan_id,
                finding_id=result.finding_id,
                tenant_id=result.tenant_id,
                actor=actor or request.actor,
                state=result.state.value,
                details={"auto": result.state == ApprovalState.AUTO_APPROVED},
            )
        return result

    def compute(
        self,
        request: ApprovalSubmitRequest,
        *,
        approval_id: Optional[UUID] = None,
    ) -> ApprovalRequest:
        evaluation = self._policy.evaluate(request)
        aid = approval_id or new_id()
        now = request.evaluated_at or utc_now()
        exp_hours = request.org_policy.default_expiration_hours
        esc_hours = request.org_policy.escalation_hours

        timeline = ApprovalTimeline(
            requested_at=now,
            expires_at=now + timedelta(hours=exp_hours),
            escalate_after=now + timedelta(hours=esc_hours),
            expected_completion=now + timedelta(hours=min(exp_hours, esc_hours + 12)),
        )

        if evaluation.auto_approve:
            auth = ExecutionAuthorization(
                authorized=True,
                approval_id=aid,
                tenant_id=request.decision.tenant_id,
                plan_id=request.plan.plan_id,
                simulation_id=request.simulation.simulation_id,
                issued_at=now,
                expires_at=timeline.expires_at,
                reason="Auto-approved by organizational policy",
            )
            decision = ApprovalDecision(
                approval_id=aid,
                state=ApprovalState.AUTO_APPROVED,
                decided_by="system:auto_approve",
                decided_at=now,
                comment=evaluation.explanation,
                auto=True,
                execution_authorization=auth,
            )
            workflow = self._workflow.build_workflow(aid, request, evaluation)
            # Mark stages skipped for auto-approve
            for stage in workflow.stages:
                stage.status = StageStatus.SKIPPED
            timeline.decided_at = now
            summary = (
                f"Auto-approved plan {request.plan.plan_id} "
                f"(risk={request.risk.risk_level})."
            )
            return ApprovalRequest(
                id=aid,
                tenant_id=request.decision.tenant_id,
                plan_id=request.plan.plan_id,
                finding_id=request.decision.finding_id,
                decision_id=request.decision.decision_id,
                simulation_id=request.simulation.simulation_id,
                asset_id=request.asset.asset_id if request.asset else None,
                state=ApprovalState.AUTO_APPROVED,
                approval_types=evaluation.approval_types,
                policy_id=evaluation.policy_id,
                policy_version=evaluation.policy_version,
                matched_rule_names=[r.name for r in evaluation.matched_rules],
                workflow=workflow,
                decision=decision,
                comments=[],
                notifications=[],
                timeline=timeline,
                assigned_approvers=[],
                summary=summary,
                explanation=evaluation.explanation,
                emergency=request.emergency,
                requester=request.requester,
                algorithm_version=ALGORITHM_VERSION,
                requested_at=now,
                first_requested_at=now,
                last_evaluated_at=now,
            )

        workflow = self._workflow.build_workflow(aid, request, evaluation)
        assignees = self._routing.list_assignees(workflow.stages)
        summary = (
            f"Approval pending for plan {request.plan.plan_id}: "
            f"{len(workflow.stages)} stage(s), "
            f"roles={[r.value for r in evaluation.required_roles]}."
        )
        approval = ApprovalRequest(
            id=aid,
            tenant_id=request.decision.tenant_id,
            plan_id=request.plan.plan_id,
            finding_id=request.decision.finding_id,
            decision_id=request.decision.decision_id,
            simulation_id=request.simulation.simulation_id,
            asset_id=request.asset.asset_id if request.asset else None,
            state=ApprovalState.PENDING,
            approval_types=evaluation.approval_types,
            policy_id=evaluation.policy_id,
            policy_version=evaluation.policy_version,
            matched_rule_names=[r.name for r in evaluation.matched_rules],
            workflow=workflow,
            decision=None,
            comments=[],
            notifications=[],
            timeline=timeline,
            assigned_approvers=assignees,
            summary=summary,
            explanation=evaluation.explanation,
            emergency=request.emergency,
            requester=request.requester,
            algorithm_version=ALGORITHM_VERSION,
            requested_at=now,
            first_requested_at=now,
            last_evaluated_at=now,
        )
        approval.notifications = self._notifications.prepare_request_notifications(
            approval
        )
        return approval

    def record_decision(
        self,
        request: RecordDecisionRequest,
        *,
        persist: bool = True,
    ) -> ApprovalRequest:
        approval = self._repo.get(request.approval_id, request.tenant_id)
        if request.comment:
            approval.comments.append(
                ApprovalComment(
                    approval_id=approval.id,
                    author=request.approver,
                    body=request.comment,
                    stage_id=request.stage_id,
                )
            )
        approval = self._workflow.apply_stage_decision(
            approval,
            approve=request.approve,
            approver=request.approver,
            stage_id=request.stage_id,
            comment=request.comment,
        )
        if approval.is_terminal:
            extra = self._notifications.prepare_decision_notifications(approval)
            approval.notifications = list(approval.notifications) + extra

        if persist:
            action = (
                AuditAction.DECISION_RECORDED
                if request.approve
                else AuditAction.REJECTED
            )
            if approval.state == ApprovalState.APPROVED:
                action = AuditAction.AUTHORIZATION_ISSUED
            approval = self._repo.save(
                approval,
                actor=request.actor or request.approver,
                change_summary=(
                    f"{'Approved' if request.approve else 'Rejected'} by "
                    f"{request.approver}"
                ),
            )
            self._audit.record(
                action=action,
                message=approval.summary,
                approval_id=approval.id,
                plan_id=approval.plan_id,
                finding_id=approval.finding_id,
                tenant_id=approval.tenant_id,
                actor=request.actor or request.approver,
                state=approval.state.value,
            )
        return approval

    def cancel(
        self,
        approval_id: UUID,
        tenant_id: UUID,
        *,
        reason: str,
        actor: Optional[str] = None,
        persist: bool = True,
    ) -> ApprovalRequest:
        approval = self._repo.get(approval_id, tenant_id)
        if approval.is_terminal:
            raise ApprovalStateError(
                f"Cannot cancel approval in state {approval.state.value}"
            )
        now = utc_now()
        approval.state = ApprovalState.CANCELLED
        approval.decision = ApprovalDecision(
            approval_id=approval.id,
            state=ApprovalState.CANCELLED,
            decided_by=actor,
            decided_at=now,
            comment=reason,
            auto=False,
            execution_authorization=ExecutionAuthorization(
                authorized=False,
                approval_id=approval.id,
                tenant_id=approval.tenant_id,
                plan_id=approval.plan_id,
                simulation_id=approval.simulation_id,
                reason=reason,
            ),
        )
        approval.timeline.decided_at = now
        approval.summary = f"Cancelled: {reason}"[:4000]
        if persist:
            approval = self._repo.save(
                approval, actor=actor, change_summary="Approval cancelled"
            )
            self._audit.record(
                action=AuditAction.CANCELLED,
                message=reason,
                approval_id=approval.id,
                plan_id=approval.plan_id,
                tenant_id=tenant_id,
                actor=actor,
                state=approval.state.value,
            )
        return approval

    def expire_if_needed(
        self,
        approval_id: UUID,
        tenant_id: UUID,
        *,
        now=None,
        persist: bool = True,
    ) -> ApprovalRequest:
        approval = self._repo.get(approval_id, tenant_id)
        now = now or utc_now()
        if approval.is_terminal:
            return approval
        if approval.timeline.expires_at and now >= approval.timeline.expires_at:
            approval.state = ApprovalState.EXPIRED
            approval.decision = ApprovalDecision(
                approval_id=approval.id,
                state=ApprovalState.EXPIRED,
                decided_by="system:expiration",
                decided_at=now,
                comment="Approval expired",
                auto=True,
                execution_authorization=ExecutionAuthorization(
                    authorized=False,
                    approval_id=approval.id,
                    tenant_id=approval.tenant_id,
                    plan_id=approval.plan_id,
                    simulation_id=approval.simulation_id,
                    reason="Approval expired before decision",
                ),
            )
            approval.timeline.decided_at = now
            if persist:
                approval = self._repo.save(
                    approval, actor="system:expiration", change_summary="Expired"
                )
                self._audit.record(
                    action=AuditAction.EXPIRED,
                    message="Approval expired",
                    approval_id=approval.id,
                    plan_id=approval.plan_id,
                    tenant_id=tenant_id,
                    actor="system:expiration",
                    state=approval.state.value,
                )
        return approval

    def escalate(
        self,
        request: EscalateApprovalRequest,
        *,
        persist: bool = True,
    ) -> ApprovalRequest:
        approval = self._repo.get(request.approval_id, request.tenant_id)
        if approval.is_terminal:
            raise ApprovalStateError(
                f"Cannot escalate approval in state {approval.state.value}"
            )
        approval.state = ApprovalState.ESCALATED
        approval.workflow.escalated = True
        approval.workflow.escalation_reason = request.reason
        role = ApproverRole.EMERGENCY_APPROVER
        if request.escalate_to_role:
            try:
                role = ApproverRole(request.escalate_to_role)
            except ValueError as exc:
                raise InvalidApprovalRequestError(
                    f"Unknown escalate_to_role: {request.escalate_to_role}"
                ) from exc
        from approval_engine.domain.models import ApprovalAssignment

        # Mark current stage escalated and add emergency assignment
        for stage in approval.workflow.stages:
            if stage.status in {StageStatus.IN_PROGRESS, StageStatus.PENDING}:
                if stage.status == StageStatus.IN_PROGRESS:
                    stage.status = StageStatus.ESCALATED
                # Deterministic directory lookup (no live IdP call)
                assignee = f"{role.value}@tenant.local"
                if role == ApproverRole.EMERGENCY_APPROVER:
                    assignee = "emergency-approver@tenant.local"
                stage.assignments.append(
                    ApprovalAssignment(
                        stage_id=stage.id,
                        approver=assignee,
                        role=role,
                        status=AssignmentStatus.PENDING,
                    )
                )
                if assignee not in approval.assigned_approvers:
                    approval.assigned_approvers.append(assignee)
                break
        notes = self._notifications.prepare_escalation_notifications(
            approval, approval.assigned_approvers[-1:]
        )
        approval.notifications = list(approval.notifications) + notes
        if persist:
            approval = self._repo.save(
                approval,
                actor=request.actor,
                change_summary=f"Escalated: {request.reason}",
            )
            self._audit.record(
                action=AuditAction.ESCALATED,
                message=request.reason,
                approval_id=approval.id,
                plan_id=approval.plan_id,
                tenant_id=request.tenant_id,
                actor=request.actor,
                state=approval.state.value,
            )
        return approval

    def delegate(
        self,
        request: DelegateApprovalRequest,
        *,
        persist: bool = True,
    ) -> ApprovalRequest:
        approval = self._repo.get(request.approval_id, request.tenant_id)
        found = False
        for stage in approval.workflow.stages:
            for assignment in stage.assignments:
                if assignment.id == request.assignment_id:
                    if assignment.approver != request.from_approver:
                        raise ApprovalStateError(
                            "Delegation from_approver does not own assignment"
                        )
                    assignment.status = AssignmentStatus.DELEGATED
                    assignment.delegated_from = request.from_approver
                    assignment.delegated_to = request.to_approver
                    from approval_engine.domain.models import ApprovalAssignment

                    stage.assignments.append(
                        ApprovalAssignment(
                            stage_id=stage.id,
                            approver=request.to_approver,
                            role=ApproverRole.DELEGATE,
                            status=AssignmentStatus.PENDING,
                            delegated_from=request.from_approver,
                        )
                    )
                    if request.to_approver not in approval.assigned_approvers:
                        approval.assigned_approvers.append(request.to_approver)
                    found = True
                    break
        if not found:
            raise ApprovalStateError("Assignment not found for delegation")
        approval.comments.append(
            ApprovalComment(
                approval_id=approval.id,
                author=request.from_approver,
                body=f"Delegated to {request.to_approver}: {request.reason}",
            )
        )
        if persist:
            approval = self._repo.save(
                approval,
                actor=request.actor or request.from_approver,
                change_summary="Approval delegated",
            )
            self._audit.record(
                action=AuditAction.DELEGATED,
                message=request.reason,
                approval_id=approval.id,
                plan_id=approval.plan_id,
                tenant_id=request.tenant_id,
                actor=request.actor or request.from_approver,
                state=approval.state.value,
                details={
                    "from": request.from_approver,
                    "to": request.to_approver,
                },
            )
        return approval

    def add_comment(
        self,
        approval_id: UUID,
        tenant_id: UUID,
        *,
        author: str,
        body: str,
        persist: bool = True,
    ) -> ApprovalRequest:
        approval = self._repo.get(approval_id, tenant_id)
        approval.comments.append(
            ApprovalComment(approval_id=approval_id, author=author, body=body)
        )
        if persist:
            approval = self._repo.save(
                approval, actor=author, change_summary="Comment added"
            )
            self._audit.record(
                action=AuditAction.COMMENT_ADDED,
                message=body[:500],
                approval_id=approval_id,
                plan_id=approval.plan_id,
                tenant_id=tenant_id,
                actor=author,
                state=approval.state.value,
            )
        return approval

    def replay(
        self,
        approval_id: UUID,
        tenant_id: UUID,
        request: ApprovalSubmitRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> ApprovalRequest:
        """Re-evaluate policy against an existing approval id (versioned replay)."""

        existing = self._repo.get(approval_id, tenant_id)
        if existing.plan_id != request.plan.plan_id:
            raise InvalidApprovalRequestError(
                "Replay plan_id must match existing approval"
            )
        recomputed = self.compute(request, approval_id=approval_id)
        recomputed.first_requested_at = existing.first_requested_at
        recomputed.current_version = existing.current_version
        if persist:
            recomputed = self._repo.save(
                recomputed,
                actor=actor or request.actor,
                change_summary="Approval policy replay",
            )
            self._audit.record(
                action=AuditAction.REPLAYED,
                message="Approval replayed against current policy",
                approval_id=recomputed.id,
                plan_id=recomputed.plan_id,
                tenant_id=tenant_id,
                actor=actor,
                state=recomputed.state.value,
            )
        return recomputed

    def get(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest:
        return self._repo.get(approval_id, tenant_id)

    def find_by_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> Optional[ApprovalRequest]:
        return self._repo.find_by_plan(plan_id, tenant_id)

    def search(
        self,
        filters: ApprovalSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[ApprovalRequest]:
        return self._repo.search(filters, page or PageRequest())

    def list_versions(self, approval_id: UUID, tenant_id: UUID):
        return self._repo.list_versions(approval_id, tenant_id)

    def authorization(
        self, approval_id: UUID, tenant_id: UUID
    ) -> Optional[ExecutionAuthorization]:
        approval = self._repo.get(approval_id, tenant_id)
        if approval.decision and approval.decision.execution_authorization:
            return approval.decision.execution_authorization
        return None
