"""Deterministic execution-type selection and step templates."""

from __future__ import annotations

from models.enums import DecisionAction, RecommendedAction
from remediation_planner.domain.enums import ExecutionType
from remediation_planner.domain.inputs import RemediationPlanRequest


def select_execution_type(request: RemediationPlanRequest) -> ExecutionType:
    """Map decision / recommended action / finding signals to ExecutionType."""

    if request.execution_type_override is not None:
        return request.execution_type_override

    decision = request.decision.decision
    if decision in {
        DecisionAction.INVESTIGATE,
        DecisionAction.MONITOR,
        DecisionAction.DEFER,
        DecisionAction.NO_ACTION,
        DecisionAction.SUPPRESS,
        DecisionAction.ESCALATE,
    }:
        return ExecutionType.MANUAL_INVESTIGATION

    action = request.decision.recommended_action
    mapping = {
        RecommendedAction.APPLY_PATCH: ExecutionType.PATCH,
        RecommendedAction.CHANGE_CONFIGURATION: ExecutionType.CONFIGURATION_CHANGE,
        RecommendedAction.ROTATE_SECRET: ExecutionType.SECRET_ROTATION,
        RecommendedAction.BLOCK_NETWORK: ExecutionType.FIREWALL_UPDATE,
        RecommendedAction.UPDATE_POLICY: ExecutionType.IAM_POLICY_CHANGE,
        RecommendedAction.ISOLATE_ASSET: ExecutionType.NETWORK_ISOLATION,
        RecommendedAction.MANUAL_REVIEW: ExecutionType.MANUAL_INVESTIGATION,
        RecommendedAction.RUN_SIMULATION: ExecutionType.MANUAL_INVESTIGATION,
        RecommendedAction.VERIFY_ONLY: ExecutionType.MANUAL_INVESTIGATION,
        RecommendedAction.OTHER: ExecutionType.CONFIGURATION_CHANGE,
        RecommendedAction.REVOKE_CREDENTIAL: ExecutionType.SECRET_ROTATION,
    }
    selected = mapping.get(action, ExecutionType.CONFIGURATION_CHANGE)

    # Finding-type heuristics (deterministic, no AI).
    ftype = (request.finding.finding_type or "").lower()
    title = (request.finding.title or "").lower()
    if "container" in ftype or "container" in title or "image" in ftype:
        return ExecutionType.CONTAINER_UPDATE
    if "package" in ftype or request.finding.package_name:
        if selected == ExecutionType.PATCH:
            return ExecutionType.PACKAGE_UPGRADE
    if request.threat_intel and (
        request.threat_intel.actively_exploited or request.threat_intel.in_cisa_kev
    ):
        if selected in {ExecutionType.PATCH, ExecutionType.PACKAGE_UPGRADE}:
            return selected
        if decision == DecisionAction.REMEDIATE:
            return ExecutionType.NETWORK_ISOLATION
    return selected


ALGORITHM_VERSION = "1.0.0"
