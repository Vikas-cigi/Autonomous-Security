"""ExecutionEngineService — facade orchestrating approved remediation execution."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from models.common import new_id, utc_now

from execution_engine.domain.enums import (
    AuditAction,
    ExecutionEventType,
    ExecutionStatus,
)
from execution_engine.domain.inputs import ExecutionRequest
from execution_engine.domain.models import (
    ALGORITHM_VERSION,
    ExecutionContext,
    ExecutionResult,
    ExecutionTimeline,
)
from execution_engine.exceptions import ExecutionStateError, InvalidExecutionRequestError
from execution_engine.interfaces.execution_repository import ExecutionRepository
from execution_engine.interfaces.rollback_repository import RollbackRepository
from execution_engine.query.filters import ExecutionSearchFilter
from execution_engine.query.pagination import Page, PageRequest
from execution_engine.services.execution_audit import ExecutionAuditService
from execution_engine.services.execution_coordinator import ExecutionCoordinator
from execution_engine.services.execution_history import ExecutionHistoryService
from execution_engine.services.execution_monitoring import ExecutionMonitoringService
from execution_engine.services.execution_step_executor import ExecutionStepExecutor
from execution_engine.services.execution_validation import ExecutionValidationService
from execution_engine.services.execution_workflow import ExecutionWorkflowService
from execution_engine.services.rollback_service import RollbackService


class ExecutionEngineService:
    """
    Execute approved remediation plans after Approval Engine.

    Pipeline: Approval → **Execution Engine** → Verification Engine.

    Never evaluates policy, recalculates trust/risk, invokes AI, or modifies plans.
    """

    def __init__(
        self,
        execution_repository: ExecutionRepository,
        *,
        rollback_repository: Optional[RollbackRepository] = None,
        validation: Optional[ExecutionValidationService] = None,
        workflow: Optional[ExecutionWorkflowService] = None,
        coordinator: Optional[ExecutionCoordinator] = None,
        monitoring: Optional[ExecutionMonitoringService] = None,
        rollback: Optional[RollbackService] = None,
        audit: Optional[ExecutionAuditService] = None,
        history: Optional[ExecutionHistoryService] = None,
        step_executor: Optional[ExecutionStepExecutor] = None,
    ) -> None:
        self._repo = execution_repository
        self._rollback_repo = rollback_repository
        self._validation = validation or ExecutionValidationService()
        self._workflow = workflow or ExecutionWorkflowService()
        self._monitor = monitoring or ExecutionMonitoringService()
        self._rollback = rollback or RollbackService(monitoring=self._monitor)
        self._steps = step_executor or ExecutionStepExecutor(monitoring=self._monitor)
        self._coordinator = coordinator or ExecutionCoordinator(
            workflow=self._workflow,
            step_executor=self._steps,
            rollback=self._rollback,
            monitoring=self._monitor,
        )
        self._audit = audit or ExecutionAuditService()
        self._history = history or ExecutionHistoryService(execution_repository)

    def execute(
        self,
        request: ExecutionRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        execution_id: Optional[UUID] = None,
        run: bool = True,
    ) -> ExecutionResult:
        self._validation.validate_start(request)
        result = self.create(request, execution_id=execution_id)
        if persist:
            result = self._repo.save(
                result,
                actor=actor or request.actor or request.initiator,
                change_summary="Execution created",
            )
            self._audit.record(
                action=AuditAction.EXECUTION_CREATED,
                message="Execution created from approved plan",
                execution_id=result.id,
                plan_id=result.plan_id,
                finding_id=result.finding_id,
                approval_id=result.approval_id,
                tenant_id=result.tenant_id,
                actor=actor or request.actor,
                status=result.status.value,
            )
        if run:
            result = self.start(
                result.id,
                result.tenant_id,
                persist=persist,
                actor=actor or request.actor,
            )
        return result

    def create(
        self,
        request: ExecutionRequest,
        *,
        execution_id: Optional[UUID] = None,
    ) -> ExecutionResult:
        eid = execution_id or new_id()
        now = request.evaluated_at or utc_now()
        plan = self._workflow.build_execution_plan(request)
        rollback_plan = self._workflow.build_rollback_plan(request)
        context = ExecutionContext(
            tenant_id=request.decision.tenant_id,
            plan_id=request.plan.plan_id,
            approval_id=request.approval.approval_id,
            authorization_id=request.authorization.authorization_id,
            decision_id=request.decision.decision_id,
            finding_id=request.decision.finding_id,
            simulation_id=request.simulation.simulation_id,
            asset_id=request.asset.asset_id if request.asset else None,
            queue_name=request.queue_name,
            initiator=request.initiator,
            environment=request.asset.environment if request.asset else None,
        )
        result = ExecutionResult(
            id=eid,
            tenant_id=request.decision.tenant_id,
            plan_id=request.plan.plan_id,
            finding_id=request.decision.finding_id,
            decision_id=request.decision.decision_id,
            approval_id=request.approval.approval_id,
            authorization_id=request.authorization.authorization_id,
            simulation_id=request.simulation.simulation_id,
            asset_id=context.asset_id,
            status=ExecutionStatus.PENDING,
            context=context,
            plan=plan,
            rollback_plan=rollback_plan,
            timeline=ExecutionTimeline(queued_at=now),
            algorithm_version=ALGORITHM_VERSION,
            last_evaluated_at=now,
        )
        self._monitor.emit(
            result, ExecutionEventType.CREATED, "Execution queued (pending)"
        )
        # Wire allow_partial from org policy into a fresh coordinator if needed
        self._coordinator = ExecutionCoordinator(
            workflow=self._workflow,
            step_executor=self._steps,
            rollback=self._rollback,
            monitoring=self._monitor,
            allow_partial_success=request.org_policy.allow_partial_success,
        )
        return result

    def start(
        self,
        execution_id: UUID,
        tenant_id: UUID,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> ExecutionResult:
        result = self._repo.get(execution_id, tenant_id)
        if result.status not in {
            ExecutionStatus.PENDING,
            ExecutionStatus.PAUSED,
            ExecutionStatus.WAITING,
        }:
            raise ExecutionStateError(
                f"Cannot start execution in state {result.status.value}"
            )
        result = self._coordinator.run(result)
        if persist:
            result = self._repo.save(
                result,
                actor=actor,
                change_summary=f"Execution {result.status.value}",
            )
            if result.rollback_execution and self._rollback_repo is not None:
                self._rollback_repo.save(
                    result.id, tenant_id, result.rollback_execution
                )
            action = AuditAction.EXECUTION_COMPLETED
            if result.status == ExecutionStatus.FAILED:
                action = AuditAction.EXECUTION_FAILED
            elif result.status == ExecutionStatus.CANCELLED:
                action = AuditAction.EXECUTION_CANCELLED
            elif result.status == ExecutionStatus.RUNNING:
                action = AuditAction.EXECUTION_STARTED
            self._audit.record(
                action=action,
                message=result.summary.headline if result.summary else result.status.value,
                execution_id=result.id,
                plan_id=result.plan_id,
                finding_id=result.finding_id,
                approval_id=result.approval_id,
                tenant_id=tenant_id,
                actor=actor,
                status=result.status.value,
            )
        return result

    def pause(
        self,
        execution_id: UUID,
        tenant_id: UUID,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> ExecutionResult:
        result = self._repo.get(execution_id, tenant_id)
        if result.is_terminal:
            raise ExecutionStateError("Cannot pause a terminal execution")
        result.pause_requested = True
        if result.status == ExecutionStatus.RUNNING:
            # Cooperative pause takes effect between steps on next start; mark paused now
            # if not actively mid-run in this process — for persisted state, set PAUSED.
            result.status = ExecutionStatus.PAUSED
            result.timeline.paused_at = utc_now()
            self._monitor.emit(result, ExecutionEventType.PAUSED, "Pause requested")
        if persist:
            result = self._repo.save(result, actor=actor, change_summary="Paused")
            self._audit.record(
                action=AuditAction.EXECUTION_PAUSED,
                message="Execution paused",
                execution_id=result.id,
                plan_id=result.plan_id,
                tenant_id=tenant_id,
                actor=actor,
                status=result.status.value,
            )
        return result

    def resume(
        self,
        execution_id: UUID,
        tenant_id: UUID,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> ExecutionResult:
        result = self._repo.get(execution_id, tenant_id)
        if result.status != ExecutionStatus.PAUSED:
            raise ExecutionStateError(
                f"Cannot resume execution in state {result.status.value}"
            )
        result.pause_requested = False
        result.timeline.resumed_at = utc_now()
        self._monitor.emit(result, ExecutionEventType.RESUMED, "Execution resumed")
        if persist:
            result = self._repo.save(result, actor=actor, change_summary="Resumed")
            self._audit.record(
                action=AuditAction.EXECUTION_RESUMED,
                message="Execution resumed",
                execution_id=result.id,
                plan_id=result.plan_id,
                tenant_id=tenant_id,
                actor=actor,
                status=result.status.value,
            )
        return self.start(execution_id, tenant_id, persist=persist, actor=actor)

    def cancel(
        self,
        execution_id: UUID,
        tenant_id: UUID,
        *,
        reason: str = "Cancelled by operator",
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> ExecutionResult:
        result = self._repo.get(execution_id, tenant_id)
        if result.is_terminal:
            raise ExecutionStateError("Cannot cancel a terminal execution")
        result.cancel_requested = True
        result.status = ExecutionStatus.CANCELLED
        result.timeline.cancelled_at = utc_now()
        result.timeline.completed_at = result.timeline.cancelled_at
        self._monitor.emit(result, ExecutionEventType.CANCELLED, reason)
        if persist:
            result = self._repo.save(result, actor=actor, change_summary=reason)
            self._audit.record(
                action=AuditAction.EXECUTION_CANCELLED,
                message=reason,
                execution_id=result.id,
                plan_id=result.plan_id,
                tenant_id=tenant_id,
                actor=actor,
                status=result.status.value,
            )
        return result

    def rollback(
        self,
        execution_id: UUID,
        tenant_id: UUID,
        *,
        reason: str = "Manual rollback requested",
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> ExecutionResult:
        result = self._repo.get(execution_id, tenant_id)
        if not result.rollback_plan.steps:
            raise InvalidExecutionRequestError("No rollback steps available")
        result.status = ExecutionStatus.ROLLING_BACK
        rb = self._rollback.build_execution(result, reason=reason)
        self._rollback.execute(result, rb)
        if result.rollback_result and result.rollback_result.status.value in {
            "completed",
            "partial",
        }:
            result.status = ExecutionStatus.ROLLED_BACK
        else:
            result.status = ExecutionStatus.FAILED
        result.timeline.completed_at = utc_now()
        self._monitor.recompute_metrics(result)
        if persist:
            result = self._repo.save(result, actor=actor, change_summary=reason)
            if result.rollback_execution and self._rollback_repo is not None:
                self._rollback_repo.save(
                    result.id, tenant_id, result.rollback_execution
                )
            self._audit.record(
                action=AuditAction.ROLLBACK_COMPLETED,
                message=reason,
                execution_id=result.id,
                plan_id=result.plan_id,
                tenant_id=tenant_id,
                actor=actor,
                status=result.status.value,
            )
        return result

    def replay(
        self,
        execution_id: UUID,
        tenant_id: UUID,
        request: ExecutionRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> ExecutionResult:
        existing = self._repo.get(execution_id, tenant_id)
        if existing.plan_id != request.plan.plan_id:
            raise InvalidExecutionRequestError(
                "Replay plan_id must match existing execution"
            )
        recomputed = self.create(request, execution_id=execution_id)
        recomputed.first_started_at = existing.first_started_at
        recomputed.current_version = existing.current_version
        self._monitor.emit(
            recomputed, ExecutionEventType.REPLAYED, "Execution replay prepared"
        )
        if persist:
            recomputed = self._repo.save(
                recomputed, actor=actor, change_summary="Execution replayed"
            )
            self._audit.record(
                action=AuditAction.REPLAYED,
                message="Execution replayed",
                execution_id=recomputed.id,
                plan_id=recomputed.plan_id,
                tenant_id=tenant_id,
                actor=actor,
                status=recomputed.status.value,
            )
        return self.start(
            recomputed.id, tenant_id, persist=persist, actor=actor
        )

    def get(self, execution_id: UUID, tenant_id: UUID) -> ExecutionResult:
        return self._repo.get(execution_id, tenant_id)

    def find_by_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> Optional[ExecutionResult]:
        return self._repo.find_by_plan(plan_id, tenant_id)

    def search(
        self,
        filters: ExecutionSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[ExecutionResult]:
        return self._repo.search(filters, page or PageRequest())

    def list_versions(self, execution_id: UUID, tenant_id: UUID):
        return self._history.list_versions(execution_id, tenant_id)
