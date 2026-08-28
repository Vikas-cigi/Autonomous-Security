"""SimulationEngineService — facade for dry-run remediation simulation."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from models.common import utc_now

from simulation_engine.domain.enums import (
    AuditAction,
    BlastRadiusTier,
    SimulationOutcome,
    StepSimulationStatus,
    WarningSeverity,
)
from simulation_engine.domain.history import SimulationAuditRecord
from simulation_engine.domain.inputs import SimulationRequest
from simulation_engine.domain.models import ALGORITHM_VERSION, SimulationResult
from simulation_engine.exceptions import InvalidSimulationRequestError
from simulation_engine.interfaces.simulation_audit_repository import (
    SimulationAuditRepository,
)
from simulation_engine.interfaces.simulation_repository import SimulationRepository
from simulation_engine.query.filters import SimulationSearchFilter
from simulation_engine.query.pagination import Page, PageRequest
from simulation_engine.services.blast_radius import BlastRadiusService
from simulation_engine.services.dependency_analysis import DependencyAnalysisService
from simulation_engine.services.impact_assessment import ImpactAssessmentService
from simulation_engine.services.policy_simulation import PolicySimulationService
from simulation_engine.services.rollback_analysis import RollbackAnalysisService


class SimulationEngineService:
    """
    Dry-run simulation of a RemediationPlan before Approval Engine.

    No infrastructure changes. No external API execution. Deterministic.
    """

    def __init__(
        self,
        simulation_repository: SimulationRepository,
        *,
        audit_repository: Optional[SimulationAuditRepository] = None,
        impact_assessment: Optional[ImpactAssessmentService] = None,
        blast_radius: Optional[BlastRadiusService] = None,
        dependency_analysis: Optional[DependencyAnalysisService] = None,
        rollback_analysis: Optional[RollbackAnalysisService] = None,
        policy_simulation: Optional[PolicySimulationService] = None,
        audit_logger: Optional[object] = None,
    ) -> None:
        self._repo = simulation_repository
        self._audit_repo = audit_repository
        self._blast = blast_radius or BlastRadiusService()
        self._deps = dependency_analysis or DependencyAnalysisService()
        self._rollback = rollback_analysis or RollbackAnalysisService()
        self._policy = policy_simulation or PolicySimulationService()
        self._impact = impact_assessment or ImpactAssessmentService(
            blast_radius=self._blast,
            dependency_analysis=self._deps,
            rollback_analysis=self._rollback,
            policy_simulation=self._policy,
        )
        self._audit = audit_logger

    def simulate(
        self,
        request: SimulationRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        simulation_id: Optional[UUID] = None,
    ) -> SimulationResult:
        self._validate(request)
        if self._audit is not None:
            self._audit.log(
                tenant_id=request.plan.tenant_id,
                action=AuditAction.SIMULATION_STARTED,
                message="Dry-run simulation started",
                actor=actor or request.actor,
                details={"plan_id": str(request.plan.plan_id)},
            )
        try:
            result = self.compute(request, simulation_id=simulation_id)
            if persist:
                result = self._repo.save(
                    result,
                    actor=actor or request.actor,
                    change_summary="Dry-run simulation completed",
                )
                if self._audit_repo is not None:
                    self._audit_repo.append(
                        SimulationAuditRecord(
                            simulation_id=result.id,
                            plan_id=result.plan_id,
                            finding_id=result.finding_id,
                            tenant_id=result.tenant_id,
                            action=AuditAction.SIMULATION_COMPLETED,
                            actor=actor or request.actor,
                            message=result.summary[:4000],
                            details={
                                "outcome": result.outcome.value,
                                "safe_to_execute": result.safe_to_execute,
                                "confidence_score": result.confidence_score,
                            },
                            outcome=result.outcome.value,
                        )
                    )
            if self._audit is not None:
                self._audit.log(
                    tenant_id=result.tenant_id,
                    action=AuditAction.SIMULATION_COMPLETED,
                    message=f"Simulation outcome={result.outcome.value}",
                    actor=actor or request.actor,
                    details={
                        "simulation_id": str(result.id),
                        "safe_to_execute": result.safe_to_execute,
                    },
                )
            return result
        except Exception as exc:
            if self._audit is not None:
                self._audit.log(
                    tenant_id=request.plan.tenant_id,
                    action=AuditAction.SIMULATION_FAILED,
                    message=str(exc)[:2000],
                    actor=actor or request.actor,
                    details={"plan_id": str(request.plan.plan_id)},
                    success=False,
                )
            raise

    def compute(
        self,
        request: SimulationRequest,
        *,
        simulation_id: Optional[UUID] = None,
    ) -> SimulationResult:
        impact, steps, warnings, assumptions = self._impact.assess(request)
        outcome, safe, confidence = self._decide(request, impact, steps, warnings)
        summary = self._summary(request, outcome, safe, impact, warnings, confidence)

        now = request.evaluated_at or utc_now()
        kwargs = {
            "tenant_id": request.plan.tenant_id,
            "plan_id": request.plan.plan_id,
            "finding_id": request.plan.finding_id,
            "decision_id": request.plan.decision_id,
            "asset_id": request.plan.asset_id
            or (request.asset.asset_id if request.asset else None),
            "outcome": outcome,
            "safe_to_execute": safe,
            "confidence_score": confidence,
            "summary": summary,
            "steps": steps,
            "impact": impact,
            "warnings": warnings,
            "affected_assets": list(impact.blast_radius.affected_asset_ids),
            "policy_violations": list(impact.policy_impact.violations),
            "assumptions": assumptions,
            "algorithm_version": ALGORITHM_VERSION,
            "current_version": 1,
            "simulated_at": now,
            "first_simulated_at": now,
            "last_simulated_at": now,
        }
        if simulation_id is not None:
            kwargs["id"] = simulation_id
        return SimulationResult(**kwargs)

    def get(self, simulation_id: UUID, tenant_id: UUID) -> SimulationResult:
        return self._repo.get(simulation_id, tenant_id)

    def find_by_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> Optional[SimulationResult]:
        return self._repo.find_by_plan(plan_id, tenant_id)

    def search(
        self,
        filters: SimulationSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[SimulationResult]:
        return self._repo.search(filters, page or PageRequest())

    def list_versions(self, simulation_id: UUID, tenant_id: UUID):
        return self._repo.list_versions(simulation_id, tenant_id)

    def _validate(self, request: SimulationRequest) -> None:
        plan = request.plan
        if not plan.steps:
            raise InvalidSimulationRequestError("Remediation plan must include steps")
        if request.asset and plan.asset_id and request.asset.asset_id != plan.asset_id:
            raise InvalidSimulationRequestError(
                "Asset snapshot asset_id does not match plan.asset_id",
                details={
                    "plan_asset_id": str(plan.asset_id),
                    "asset_id": str(request.asset.asset_id),
                },
            )
        sequences = [s.sequence for s in plan.steps]
        if len(sequences) != len(set(sequences)):
            raise InvalidSimulationRequestError("Plan step sequences must be unique")

    def _decide(
        self,
        request: SimulationRequest,
        impact,
        steps,
        warnings,
    ) -> tuple[SimulationOutcome, bool, float]:
        critical = [
            w for w in warnings if w.severity == WarningSeverity.CRITICAL
        ]
        blocked_steps = [
            s for s in steps if s.status == StepSimulationStatus.BLOCKED
        ]
        policy_blocked = impact.policy_impact.has_blocking_violation
        rollback_ok = impact.rollback.rollback_possible
        wide = impact.blast_radius.tier in {
            BlastRadiusTier.ENVIRONMENT,
            BlastRadiusTier.TENANT,
        }

        # Confidence: start high, discount for missing data / conflicts
        confidence = 0.92
        if request.asset is None:
            confidence -= 0.12
        if request.threat_intel is None:
            confidence -= 0.04
        if impact.policy_impact.conflicts:
            confidence -= 0.05 * min(3, len(impact.policy_impact.conflicts))
        if impact.dependency_impact.cascading_risk >= 0.7:
            confidence -= 0.08
        confidence = round(max(0.35, min(0.99, confidence)), 4)

        if policy_blocked or blocked_steps or (
            not rollback_ok and any(s.is_destructive for s in request.plan.steps)
        ):
            return SimulationOutcome.UNSAFE, False, confidence

        if critical or wide or impact.downtime.maintenance_window_recommended:
            # Conditional: may execute after approval / window
            safe = not policy_blocked and rollback_ok
            if wide and impact.blast_radius.tier == BlastRadiusTier.TENANT:
                return SimulationOutcome.CONDITIONAL, False, confidence
            return SimulationOutcome.CONDITIONAL, safe, confidence

        if confidence < 0.5:
            return SimulationOutcome.INCONCLUSIVE, False, confidence

        return SimulationOutcome.SAFE, True, confidence

    def _summary(
        self,
        request: SimulationRequest,
        outcome: SimulationOutcome,
        safe: bool,
        impact,
        warnings: List,
        confidence: float,
    ) -> str:
        plan = request.plan
        parts = [
            f"Dry-run simulation for plan {plan.plan_id}: outcome={outcome.value}, "
            f"safe_to_execute={'yes' if safe else 'no'}.",
            f"Blast radius={impact.blast_radius.tier.value}; "
            f"downtime≈{impact.downtime.seconds}s; "
            f"rollback={'possible' if impact.rollback.rollback_possible else 'not possible'}.",
            f"Risk {impact.risk_reduction.current_risk_score:.1f} → "
            f"{impact.risk_reduction.predicted_risk_score:.1f} "
            f"(reduction≈{impact.risk_reduction.reduction_ratio:.0%}).",
            f"Affected assets={len(impact.blast_radius.affected_asset_ids)}; "
            f"warnings={len(warnings)}; "
            f"policy_violations={len(impact.policy_impact.violations)}; "
            f"confidence={confidence:.2f}.",
        ]
        if impact.downtime.maintenance_window_recommended:
            parts.append("Maintenance window recommended before execution.")
        if impact.policy_impact.violations:
            parts.append(
                "Policy violations: " + "; ".join(impact.policy_impact.violations[:5])
            )
        return " ".join(parts)[:8000]
