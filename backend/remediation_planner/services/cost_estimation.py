"""CostEstimationService — relative remediation cost bands."""

from __future__ import annotations

from typing import List

from remediation_planner.domain.enums import CostBand, ExecutionType
from remediation_planner.domain.inputs import RemediationPlanRequest
from remediation_planner.domain.models import EstimatedDuration, RemediationCost, RemediationStep


class CostEstimationService:
    """Deterministic relative cost estimate (not a financial invoice)."""

    BASE_LABOR = {
        ExecutionType.MANUAL_INVESTIGATION: 2.0,
        ExecutionType.CONFIGURATION_CHANGE: 1.0,
        ExecutionType.FIREWALL_UPDATE: 0.75,
        ExecutionType.IAM_POLICY_CHANGE: 1.25,
        ExecutionType.SECRET_ROTATION: 2.5,
        ExecutionType.PATCH: 1.5,
        ExecutionType.PACKAGE_UPGRADE: 1.5,
        ExecutionType.CONTAINER_UPDATE: 2.0,
        ExecutionType.NETWORK_ISOLATION: 1.0,
    }

    def estimate(
        self,
        request: RemediationPlanRequest,
        steps: List[RemediationStep],
        duration: EstimatedDuration,
        execution_type: ExecutionType,
    ) -> RemediationCost:
        base = self.BASE_LABOR.get(execution_type, 1.0)
        crit = request.asset.criticality if request.asset else 0.5
        labor = round(base * (1.0 + 0.5 * crit) + duration.total_seconds / 3600.0, 2)
        infra = 0.0
        if execution_type in {
            ExecutionType.CONTAINER_UPDATE,
            ExecutionType.PACKAGE_UPGRADE,
            ExecutionType.PATCH,
        }:
            infra = round(0.2 + 0.3 * crit, 2)

        relative = round(min(1.0, (labor / 8.0) * 0.7 + infra * 0.3), 4)
        band = self._band(relative)
        return RemediationCost(
            band=band,
            relative_score=relative,
            labor_hours=labor,
            infrastructure_units=infra,
            explanation=(
                f"Relative cost band={band.value} from labor≈{labor:.1f}h "
                f"and infra_units={infra:.2f} for {execution_type.value} "
                f"({len(steps)} steps)."
            ),
        )

    @staticmethod
    def _band(score: float) -> CostBand:
        if score < 0.15:
            return CostBand.NEGLIGIBLE
        if score < 0.35:
            return CostBand.LOW
        if score < 0.60:
            return CostBand.MEDIUM
        if score < 0.85:
            return CostBand.HIGH
        return CostBand.VERY_HIGH
