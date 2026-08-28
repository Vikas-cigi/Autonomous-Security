"""Route approval stages to organizational approver identities."""

from __future__ import annotations

from typing import Dict, List

from approval_engine.domain.enums import ApproverRole, AssignmentStatus
from approval_engine.domain.inputs import ApprovalSubmitRequest
from approval_engine.domain.models import ApprovalAssignment, ApprovalStage
from models.common import new_id


# Deterministic role → mailbox / identity mapping (tenant-agnostic placeholders).
# Callers / IdP adapters can rewrite these later; engine stays offline.
_ROLE_DIRECTORY: Dict[ApproverRole, str] = {
    ApproverRole.SECURITY_MANAGER: "security-manager@tenant.local",
    ApproverRole.INFRASTRUCTURE_MANAGER: "infra-manager@tenant.local",
    ApproverRole.NETWORK_TEAM: "network-team@tenant.local",
    ApproverRole.SECURITY_APPROVER: "security-approver@tenant.local",
    ApproverRole.OPERATIONS_MANAGER: "ops-manager@tenant.local",
    ApproverRole.COMPLIANCE_OFFICER: "compliance@tenant.local",
    ApproverRole.CHANGE_MANAGER: "change-manager@tenant.local",
    ApproverRole.BUSINESS_OWNER: "business-owner@tenant.local",
    ApproverRole.DELEGATE: "delegate@tenant.local",
    ApproverRole.EMERGENCY_APPROVER: "emergency-approver@tenant.local",
}


class ApprovalRoutingService:
    """Assign approver identities to workflow stages (no external calls)."""

    def resolve_approver(
        self,
        role: ApproverRole,
        request: ApprovalSubmitRequest,
    ) -> str:
        # Business owner can be asset hostname owner placeholder
        if role == ApproverRole.BUSINESS_OWNER and request.asset and request.asset.hostname:
            return f"owner:{request.asset.hostname}"
        return _ROLE_DIRECTORY.get(role, f"{role.value}@tenant.local")

    def assign_stage(
        self,
        stage: ApprovalStage,
        request: ApprovalSubmitRequest,
    ) -> ApprovalStage:
        approver = self.resolve_approver(stage.required_role, request)
        assignment = ApprovalAssignment(
            id=new_id(),
            stage_id=stage.id,
            approver=approver,
            role=stage.required_role,
            status=AssignmentStatus.PENDING,
        )
        stage.assignments = [assignment]
        return stage

    def list_assignees(self, stages: List[ApprovalStage]) -> List[str]:
        names: List[str] = []
        for stage in stages:
            for a in stage.assignments:
                if a.approver not in names:
                    names.append(a.approver)
        return names
