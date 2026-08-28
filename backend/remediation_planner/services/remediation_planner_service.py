"""RemediationPlannerService — facade orchestrating deterministic planning."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from models.common import utc_now
from models.enums import DecisionAction

from remediation_planner.domain.catalog import ALGORITHM_VERSION, select_execution_type
from remediation_planner.domain.enums import AuditAction
from remediation_planner.domain.inputs import RemediationPlanRequest
from remediation_planner.domain.models import RemediationPlan
from remediation_planner.exceptions import (
    InvalidPlanRequestError,
    UnsupportedDecisionForPlanningError,
)
from remediation_planner.interfaces.remediation_history_repository import (
    RemediationHistoryRepository,
)
from remediation_planner.interfaces.remediation_plan_repository import (
    RemediationPlanRepository,
)
from remediation_planner.query.filters import RemediationPlanSearchFilter
from remediation_planner.query.pagination import Page, PageRequest
from remediation_planner.services.cost_estimation import CostEstimationService
from remediation_planner.services.dependency_resolution import DependencyResolutionService
from remediation_planner.services.impact_analysis import ImpactAnalysisService
from remediation_planner.services.plan_generation import PlanGenerationService
from remediation_planner.services.rollback_planning import RollbackPlanningService


class RemediationPlannerService:
    """
    Convert an approved DecisionObject snapshot into a RemediationPlan.

    Pipeline: after Decision Service, before Simulation Engine / AI Harness.
    No AI. No infrastructure execution.
    """

    PLANABLE_ACTIONS = {
        DecisionAction.REMEDIATE,
        DecisionAction.MITIGATE,
        DecisionAction.INVESTIGATE,
        DecisionAction.MONITOR,
        DecisionAction.ESCALATE,
    }

    def __init__(
        self,
        plan_repository: RemediationPlanRepository,
        *,
        history_repository: Optional[RemediationHistoryRepository] = None,
        plan_generation: Optional[PlanGenerationService] = None,
        dependency_resolution: Optional[DependencyResolutionService] = None,
        rollback_planning: Optional[RollbackPlanningService] = None,
        impact_analysis: Optional[ImpactAnalysisService] = None,
        cost_estimation: Optional[CostEstimationService] = None,
        audit_logger: Optional[object] = None,
    ) -> None:
        self._repo = plan_repository
        self._history = history_repository
        self._generation = plan_generation or PlanGenerationService()
        self._dependencies = dependency_resolution or DependencyResolutionService()
        self._rollback = rollback_planning or RollbackPlanningService()
        self._impact = impact_analysis or ImpactAnalysisService()
        self._cost = cost_estimation or CostEstimationService()
        self._audit = audit_logger

    def plan(
        self,
        request: RemediationPlanRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        plan_id: Optional[UUID] = None,
    ) -> RemediationPlan:
        self._validate(request)
        result = self.compute(request, plan_id=plan_id)
        if persist:
            result = self._repo.save(
                result,
                actor=actor or request.actor,
                change_summary="Remediation plan generated",
            )
            if self._audit is not None:
                self._audit.log(
                    tenant_id=result.tenant_id,
                    action=AuditAction.PLAN_GENERATED,
                    message=f"Generated {result.execution_type.value} plan",
                    actor=actor or request.actor,
                    details={
                        "plan_id": str(result.id),
                        "finding_id": str(result.finding_id),
                        "decision_id": str(result.decision_id),
                        "steps": len(result.steps),
                    },
                )
        return result

    def compute(
        self,
        request: RemediationPlanRequest,
        *,
        plan_id: Optional[UUID] = None,
    ) -> RemediationPlan:
        execution_type = select_execution_type(request)
        steps, tasks, validations = self._generation.generate(request, execution_type)
        graph = self._dependencies.resolve(steps)
        target = (
            request.asset.hostname
            if request.asset and request.asset.hostname
            else f"asset:{request.finding.asset_id}"
        )
        rollback = self._rollback.build(steps, execution_type, target=target)
        impact, duration, approval, window, status = self._impact.analyze(
            request, steps, execution_type
        )
        cost = self._cost.estimate(request, steps, duration, execution_type)

        summary = (
            f"{execution_type.value.replace('_', ' ').title()} plan for finding "
            f"{request.finding.finding_id} "
            f"(decision={request.decision.decision.value})."
        )
        change_summary = (
            f"{len(steps)} steps, {len(tasks)} tasks, "
            f"downtime≈{impact.downtime_seconds}s, "
            f"cost={cost.band.value}, "
            f"risk_reduction≈{impact.risk_reduction_estimate:.0%}."
        )
        explanation = self._explanation(
            request, execution_type, steps, impact, duration, cost, approval
        )

        now = request.evaluated_at or utc_now()
        kwargs = {
            "tenant_id": request.decision.tenant_id,
            "finding_id": request.decision.finding_id,
            "decision_id": request.decision.decision_id,
            "asset_id": request.finding.asset_id,
            "status": status,
            "execution_type": execution_type,
            "decision_action": request.decision.decision,
            "recommended_action": request.decision.recommended_action,
            "priority": request.decision.priority,
            "summary": summary,
            "explanation": explanation,
            "change_summary": change_summary,
            "steps": steps,
            "execution_tasks": tasks,
            "validation_checks": validations,
            "dependency_graph": graph,
            "rollback_plan": rollback,
            "estimated_impact": impact,
            "estimated_duration": duration,
            "cost_estimate": cost,
            "approval_requirement": approval,
            "change_window": window,
            "policy_version": request.policy.policy_version
            or request.decision.policy_version,
            "related_policy_ids": list(
                request.policy.related_policy_ids or request.decision.related_policy_ids
            ),
            "algorithm_version": ALGORITHM_VERSION,
            "planned_at": now,
            "first_planned_at": now,
            "last_planned_at": now,
        }
        if plan_id is not None:
            kwargs["id"] = plan_id
        return RemediationPlan(**kwargs)

    def get_for_finding(
        self, finding_id: UUID, tenant_id: UUID
    ) -> Optional[RemediationPlan]:
        return self._repo.find_by_finding(finding_id, tenant_id)

    def get_for_decision(
        self, decision_id: UUID, tenant_id: UUID
    ) -> Optional[RemediationPlan]:
        return self._repo.find_by_decision(decision_id, tenant_id)

    def get_plan(self, plan_id: UUID, tenant_id: UUID) -> RemediationPlan:
        return self._repo.get(plan_id, tenant_id)

    def search(
        self,
        filters: RemediationPlanSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[RemediationPlan]:
        return self._repo.search(filters, page or PageRequest())

    def _validate(self, request: RemediationPlanRequest) -> None:
        if request.finding.finding_id != request.decision.finding_id:
            raise InvalidPlanRequestError(
                "finding.finding_id must match decision.finding_id"
            )
        if request.finding.tenant_id != request.decision.tenant_id:
            raise InvalidPlanRequestError(
                "finding.tenant_id must match decision.tenant_id"
            )
        if (
            request.asset is not None
            and request.asset.asset_id != request.finding.asset_id
        ):
            raise InvalidPlanRequestError("asset.asset_id must match finding.asset_id")
        if request.decision.decision not in self.PLANABLE_ACTIONS:
            raise UnsupportedDecisionForPlanningError(
                f"Decision action {request.decision.decision.value} is not planable",
                details={"decision": request.decision.decision.value},
            )

    @staticmethod
    def _explanation(
        request,
        execution_type,
        steps,
        impact,
        duration,
        cost,
        approval,
    ) -> str:
        title = request.finding.title or "untitled finding"
        return (
            f"Planned {execution_type.value} remediation for '{title}'. "
            f"{len(steps)} ordered steps; estimated duration "
            f"{duration.human_summary}; blast radius "
            f"{impact.blast_radius.value}; cost band {cost.band.value}. "
            f"Approval required={approval.required}. "
            f"Risk reduction estimate={impact.risk_reduction_estimate:.0%}. "
            f"Decision reason: {request.decision.reason[:500]}"
        )
