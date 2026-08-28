"""Dependency analysis for dry-run remediation simulation."""

from __future__ import annotations

from simulation_engine.domain.inputs import SimulationRequest
from simulation_engine.domain.models import DependencyImpact


class DependencyAnalysisService:
    """Analyze asset/service dependency impact without live graph queries."""

    def analyze(self, request: SimulationRequest) -> DependencyImpact:
        asset = request.asset
        plan = request.plan

        if asset is None:
            return DependencyImpact(
                dependent_asset_count=0,
                dependent_service_count=0,
                cascading_risk=0.15,
                blocked_by_missing_dependency=False,
                explanation=(
                    "No asset snapshot provided; dependency impact uses conservative "
                    "defaults and is not blocked."
                ),
            )

        dep_assets = len(asset.dependent_asset_ids)
        dep_services = len(asset.dependent_services)
        destructive = any(s.is_destructive for s in plan.steps)
        missing_deps = any(
            s.depends_on_sequences and max(s.depends_on_sequences) >= s.sequence
            for s in plan.steps
        )
        # Also flag if step depends on sequence that does not exist
        known = {s.sequence for s in plan.steps}
        for step in plan.steps:
            for dep_seq in step.depends_on_sequences:
                if dep_seq not in known:
                    missing_deps = True
                    break

        cascading = min(
            1.0,
            0.1
            + (dep_assets * 0.05)
            + (dep_services * 0.04)
            + (0.2 if destructive else 0.0)
            + (asset.criticality * 0.25),
        )

        explanation = (
            f"{dep_assets} dependent asset(s), {dep_services} dependent service(s); "
            f"cascading_risk={cascading:.2f}."
        )
        if missing_deps:
            explanation += " Plan has unresolved step dependency references."

        return DependencyImpact(
            dependent_asset_count=dep_assets,
            dependent_service_count=dep_services,
            cascading_risk=round(cascading, 4),
            blocked_by_missing_dependency=missing_deps,
            explanation=explanation,
        )
