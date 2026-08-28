"""Impact assessment aggregation for dry-run remediation simulation."""

from __future__ import annotations

from datetime import timedelta
from typing import List, Tuple

from simulation_engine.domain.enums import (
    BlastRadiusTier,
    StepSimulationStatus,
    WarningSeverity,
)
from simulation_engine.domain.inputs import SimulationRequest
from simulation_engine.domain.models import (
    BlastRadius,
    DependencyImpact,
    DowntimeEstimate,
    ImpactAssessment,
    PolicyImpact,
    RiskReductionEstimate,
    RollbackAssessment,
    SimulationStep,
    SimulationWarning,
)
from simulation_engine.services.blast_radius import BlastRadiusService
from simulation_engine.services.dependency_analysis import DependencyAnalysisService
from simulation_engine.services.policy_simulation import PolicySimulationService
from simulation_engine.services.rollback_analysis import RollbackAnalysisService


class ImpactAssessmentService:
    """
    Compose blast radius, dependencies, downtime, rollback, policy, and risk
    reduction into a single ImpactAssessment.
    """

    def __init__(
        self,
        *,
        blast_radius: BlastRadiusService | None = None,
        dependency_analysis: DependencyAnalysisService | None = None,
        rollback_analysis: RollbackAnalysisService | None = None,
        policy_simulation: PolicySimulationService | None = None,
    ) -> None:
        self._blast = blast_radius or BlastRadiusService()
        self._deps = dependency_analysis or DependencyAnalysisService()
        self._rollback = rollback_analysis or RollbackAnalysisService()
        self._policy = policy_simulation or PolicySimulationService()

    def assess(
        self, request: SimulationRequest
    ) -> Tuple[ImpactAssessment, List[SimulationStep], List[SimulationWarning], List[str]]:
        blast = self._blast.estimate(request)
        deps = self._deps.analyze(request)
        rollback = self._rollback.assess(request)
        downtime = self._estimate_downtime(request, blast, deps)
        policy = self._policy.evaluate(
            request, downtime=downtime, rollback=rollback
        )
        risk = self._estimate_risk_reduction(request, deps, rollback, policy)
        compliance = self._compliance_notes(request, policy)

        steps = self._simulate_steps(request, deps, policy)
        warnings = self._warnings(request, blast, deps, rollback, policy, downtime)

        impact = ImpactAssessment(
            blast_radius=blast,
            downtime=downtime,
            dependency_impact=deps,
            rollback=rollback,
            policy_impact=policy,
            risk_reduction=risk,
            compliance_impact_notes=compliance,
        )
        assumptions = [
            "Dry-run only; no infrastructure or adapter APIs were invoked.",
            "Asset dependency graph taken from caller-provided snapshot.",
            f"Policy constraints evaluated against version {request.policy.policy_version}.",
            f"Algorithm version stamped on result envelope.",
        ]
        return impact, steps, warnings, assumptions

    def _estimate_downtime(
        self,
        request: SimulationRequest,
        blast: BlastRadius,
        deps: DependencyImpact,
    ) -> DowntimeEstimate:
        plan = request.plan
        step_seconds = sum(s.estimated_duration_seconds for s in plan.steps)
        planned = plan.planned_downtime_seconds
        seconds = max(planned, step_seconds)

        # Cascading buffer for dependent services
        buffer = int(seconds * deps.cascading_risk * 0.25)
        seconds = seconds + buffer

        env = (request.asset.environment or "").lower() if request.asset else ""
        maintenance = (
            plan.change_window_required
            or seconds >= 300
            or blast.tier
            in {BlastRadiusTier.ENVIRONMENT, BlastRadiusTier.TENANT}
            or env in {"production", "prod"}
        )

        start = None
        end = None
        if maintenance:
            # Recommend next calendar day 02:00–04:00 UTC relative to evaluated_at
            base = request.evaluated_at
            start = (base + timedelta(days=1)).replace(
                hour=2, minute=0, second=0, microsecond=0
            )
            end = start + timedelta(hours=2)

        explanation = (
            f"Estimated downtime {seconds}s "
            f"(steps={step_seconds}s, planned={planned}s, buffer={buffer}s)."
        )
        if maintenance:
            explanation += " Maintenance window recommended."

        return DowntimeEstimate(
            seconds=seconds,
            maintenance_window_recommended=maintenance,
            preferred_window_start=start,
            preferred_window_end=end,
            explanation=explanation,
        )

    def _estimate_risk_reduction(
        self,
        request: SimulationRequest,
        deps: DependencyImpact,
        rollback: RollbackAssessment,
        policy: PolicyImpact,
    ) -> RiskReductionEstimate:
        current = request.risk.enterprise_risk_score
        planned = request.plan.estimated_risk_reduction
        if planned is None:
            # Default: higher risk → larger expected reduction for remediations
            planned = min(0.85, 0.35 + (current / 100.0) * 0.4)

        residual_ops = min(
            1.0,
            deps.cascading_risk * 0.5
            + (0.2 if not rollback.rollback_possible else 0.05)
            + (0.15 if policy.has_blocking_violation else 0.0),
        )
        reduction = max(0.0, planned * (1.0 - residual_ops * 0.35))
        predicted = max(0.0, round(current * (1.0 - reduction), 4))

        ti = request.threat_intel
        explanation = (
            f"Current risk {current:.2f} → predicted {predicted:.2f} "
            f"(reduction_ratio={reduction:.2%})."
        )
        if ti and (ti.in_cisa_kev or ti.actively_exploited):
            explanation += " Active exploitation context increases urgency of remediation."

        return RiskReductionEstimate(
            current_risk_score=current,
            predicted_risk_score=predicted,
            reduction_ratio=round(reduction, 4),
            residual_operational_risk=round(residual_ops, 4),
            explanation=explanation,
        )

    def _compliance_notes(
        self, request: SimulationRequest, policy: PolicyImpact
    ) -> List[str]:
        notes: List[str] = []
        tags = request.asset.compliance_tags if request.asset else []
        if tags:
            notes.append(
                f"Asset compliance tags in scope: {', '.join(tags[:20])}."
            )
        if policy.requires_change_window:
            notes.append("Change window required for compliance-sensitive change.")
        if policy.requires_approval:
            notes.append("Human approval required before execution.")
        if request.risk.compliance_impact and request.risk.compliance_impact >= 0.7:
            notes.append("High compliance impact on risk assessment.")
        return notes

    def _simulate_steps(
        self,
        request: SimulationRequest,
        deps: DependencyImpact,
        policy: PolicyImpact,
    ) -> List[SimulationStep]:
        steps: List[SimulationStep] = []
        blocked = deps.blocked_by_missing_dependency or policy.has_blocking_violation
        for step in request.plan.steps:
            if blocked and step.is_destructive:
                status = StepSimulationStatus.BLOCKED
                notes = "Blocked by dependency or policy violation."
            elif step.is_destructive:
                status = StepSimulationStatus.PREDICTED_RISK
                notes = "Destructive step; predicted success with elevated risk."
            else:
                status = StepSimulationStatus.PREDICTED_SUCCESS
                notes = "Dry-run predicts successful completion."
            steps.append(
                SimulationStep(
                    step_id=step.step_id,
                    sequence=step.sequence,
                    action=step.action,
                    target=step.target,
                    status=status,
                    predicted_duration_seconds=step.estimated_duration_seconds,
                    is_destructive=step.is_destructive,
                    notes=notes,
                )
            )
        return steps

    def _warnings(
        self,
        request: SimulationRequest,
        blast: BlastRadius,
        deps: DependencyImpact,
        rollback: RollbackAssessment,
        policy: PolicyImpact,
        downtime: DowntimeEstimate,
    ) -> List[SimulationWarning]:
        warnings: List[SimulationWarning] = []
        if request.asset is None:
            warnings.append(
                SimulationWarning(
                    code="MISSING_ASSET",
                    severity=WarningSeverity.WARNING,
                    message="Asset inventory snapshot missing; impact estimates are conservative.",
                )
            )
        if deps.blocked_by_missing_dependency:
            warnings.append(
                SimulationWarning(
                    code="DEPENDENCY_GAP",
                    severity=WarningSeverity.CRITICAL,
                    message=deps.explanation,
                )
            )
        if not rollback.rollback_possible:
            warnings.append(
                SimulationWarning(
                    code="ROLLBACK_GAP",
                    severity=WarningSeverity.CRITICAL,
                    message="; ".join(rollback.gaps) or rollback.explanation,
                )
            )
        for v in policy.violations:
            warnings.append(
                SimulationWarning(
                    code="POLICY_VIOLATION",
                    severity=WarningSeverity.CRITICAL,
                    message=v,
                )
            )
        for c in policy.conflicts:
            warnings.append(
                SimulationWarning(
                    code="POLICY_CONFLICT",
                    severity=WarningSeverity.WARNING,
                    message=c,
                )
            )
        if blast.tier in {BlastRadiusTier.ENVIRONMENT, BlastRadiusTier.TENANT}:
            warnings.append(
                SimulationWarning(
                    code="WIDE_BLAST_RADIUS",
                    severity=WarningSeverity.WARNING,
                    message=f"Estimated blast radius is {blast.tier.value}.",
                )
            )
        if downtime.maintenance_window_recommended:
            warnings.append(
                SimulationWarning(
                    code="MAINTENANCE_WINDOW",
                    severity=WarningSeverity.INFO,
                    message="Maintenance window recommended before execution.",
                )
            )
        return warnings
