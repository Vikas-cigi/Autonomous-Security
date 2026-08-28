"""Blast radius estimation for dry-run remediation simulation."""

from __future__ import annotations

from typing import List
from uuid import UUID

from simulation_engine.domain.enums import BlastRadiusTier
from simulation_engine.domain.inputs import SimulationRequest
from simulation_engine.domain.models import BlastRadius


class BlastRadiusService:
    """
    Estimate blast radius without contacting infrastructure.

    Deterministic: same request → same tier and asset set.
    """

    def estimate(self, request: SimulationRequest) -> BlastRadius:
        plan = request.plan
        asset = request.asset
        affected: List[UUID] = []
        services: List[str] = []

        if plan.asset_id:
            affected.append(plan.asset_id)
        if asset:
            for dep in asset.dependent_asset_ids:
                if dep not in affected:
                    affected.append(dep)
            services.extend(list(asset.dependent_services))

        destructive = any(s.is_destructive for s in plan.steps)
        dep_count = len(asset.dependent_asset_ids) if asset else 0
        criticality = asset.criticality if asset else 0.5
        env = (asset.environment or "").lower() if asset else ""

        if not affected and not services:
            tier = BlastRadiusTier.NONE
            explanation = "No target asset or dependents declared; blast radius is none."
        elif dep_count == 0 and not destructive:
            tier = BlastRadiusTier.ASSET
            explanation = "Impact limited to the primary asset; no dependents declared."
        elif dep_count <= 3 and env not in {"production", "prod"}:
            tier = BlastRadiusTier.GROUP
            explanation = (
                f"Affects primary asset plus {dep_count} dependent asset(s) "
                f"in non-production context."
            )
        elif dep_count <= 10 or (destructive and criticality >= 0.7):
            tier = BlastRadiusTier.ENVIRONMENT
            explanation = (
                f"Destructive or broadly dependent change ({dep_count} dependents, "
                f"criticality={criticality:.2f}) may impact the environment."
            )
        else:
            tier = BlastRadiusTier.TENANT
            explanation = (
                "High fan-out dependency graph or tenant-wide service exposure "
                "elevates blast radius to tenant scope."
            )

        if services and tier == BlastRadiusTier.ASSET:
            tier = BlastRadiusTier.GROUP
            explanation = (
                "Dependent services present; blast radius elevated to group scope."
            )

        return BlastRadius(
            tier=tier,
            affected_asset_ids=affected,
            affected_services=services[:50],
            explanation=explanation,
        )
