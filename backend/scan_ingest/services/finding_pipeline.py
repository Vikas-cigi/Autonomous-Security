"""FindingPipelineService — Trust → Risk → Decision → Planner after ingest."""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence
from uuid import UUID

from models.common import ActorReference
from models.enums import DecisionAction, Severity
from models.security_finding import SecurityFindingObject
from risk_engine.domain.builders import build_risk_scoring_input
from scan_ingest.domain.models import IngestedFindingSummary, PipelineFindingResult
from trust_scoring.domain.builders import build_scoring_input

logger = logging.getLogger(__name__)

_SEVERITY_HINT = {
    Severity.CRITICAL: 1.0,
    Severity.HIGH: 0.8,
    Severity.MEDIUM: 0.5,
    Severity.LOW: 0.25,
    Severity.INFORMATIONAL: 0.05,
    Severity.UNKNOWN: 0.4,
}

_PLAN_ACTIONS = {
    DecisionAction.REMEDIATE,
    DecisionAction.MITIGATE,
    DecisionAction.ESCALATE,
}


class FindingPipelineService:
    """
    Chains enterprise engines for newly ingested findings.

    Callers supply already-built engine facades sharing their own sessions.
    Never reaches into sibling ORM tables beyond the finding objects provided.
    """

    def __init__(
        self,
        *,
        trust_scoring: Any,
        risk_engine: Any,
        decision_service: Any,
        planner: Any,
        evidence_repository: Any,
    ) -> None:
        self._trust = trust_scoring
        self._risk = risk_engine
        self._decision = decision_service
        self._planner = planner
        self._evidence = evidence_repository

    async def run_for_findings(
        self,
        summaries: Sequence[IngestedFindingSummary],
        *,
        tenant_id: UUID,
        owner: ActorReference,
        asset_id: Optional[UUID] = None,
        invoke_ai: bool = False,
        only_created: bool = True,
    ) -> List[PipelineFindingResult]:
        results: List[PipelineFindingResult] = []
        for summary in summaries:
            if only_created and not summary.created:
                results.append(
                    PipelineFindingResult(
                        finding_id=summary.finding_id,
                        skipped_reason="merged_duplicate",
                    )
                )
                continue
            try:
                result = await self.run_one(
                    summary.finding_id,
                    tenant_id=tenant_id,
                    owner=owner,
                    asset_id=asset_id,
                    invoke_ai=invoke_ai,
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Pipeline failed finding=%s", summary.finding_id)
                results.append(
                    PipelineFindingResult(
                        finding_id=summary.finding_id,
                        error=str(exc),
                    )
                )
        return results

    async def run_one(
        self,
        finding_id: UUID,
        *,
        tenant_id: UUID,
        owner: ActorReference,
        asset_id: Optional[UUID] = None,
        invoke_ai: bool = False,
    ) -> PipelineFindingResult:
        finding = self._load_finding(finding_id, tenant_id)
        out = PipelineFindingResult(finding_id=finding.id)

        trust_input = build_scoring_input(finding)
        trust = self._trust.score(trust_input)
        out.trust_score = trust.trust_score.value
        out.trust_level = (
            trust.trust_score.level.value
            if hasattr(trust.trust_score.level, "value")
            else str(trust.trust_score.level)
        )

        severity = finding.severity
        if not isinstance(severity, Severity):
            try:
                severity = Severity(str(severity).lower())
            except ValueError:
                severity = Severity.UNKNOWN

        risk_input = build_risk_scoring_input(
            finding_id=finding.id,
            tenant_id=finding.tenant_id,
            asset_id=finding.asset_id,
            trust_score=trust.trust_score.value,
            severity_hint=_SEVERITY_HINT.get(severity, 0.4),
            cvss_base_score=finding.cvss_score,
            evidence_count=len(finding.evidence),
            validated_evidence_count=len(finding.evidence),
            average_evidence_confidence=(
                sum(e.confidence for e in finding.evidence) / len(finding.evidence)
                if finding.evidence
                else 0.0
            ),
            trust_level=out.trust_level,
            recommendation_confidence=(
                trust.recommendation_confidence.value
                if hasattr(trust.recommendation_confidence, "value")
                else str(trust.recommendation_confidence)
            ),
            asset_criticality=0.5,
        )
        risk = self._risk.score(risk_input)
        out.risk_score = risk.enterprise_risk_score.value
        out.risk_level = (
            risk.risk_level.value
            if hasattr(risk.risk_level, "value")
            else str(risk.risk_level)
        )

        from decision_service.domain.inputs import (
            AssetSnapshot,
            DecisionRequest,
            FindingSnapshot,
            RiskSnapshot,
            TrustSnapshot,
        )

        decision_req = DecisionRequest(
            finding=FindingSnapshot(
                finding_id=finding.id,
                tenant_id=finding.tenant_id,
                asset_id=finding.asset_id,
                title=finding.title,
                severity=severity.value,
                finding_type=(
                    finding.finding_type.value
                    if hasattr(finding.finding_type, "value")
                    else str(finding.finding_type)
                ),
                cve_ids=list(finding.cve_ids or []),
                summary=finding.description[:500] if finding.description else None,
            ),
            trust=TrustSnapshot(
                trust_score=trust.trust_score.value,
                trust_level=out.trust_level,
                recommendation_confidence=(
                    trust.recommendation_confidence.value
                    if hasattr(trust.recommendation_confidence, "value")
                    else str(trust.recommendation_confidence)
                ),
            ),
            risk=RiskSnapshot(
                enterprise_risk_score=risk.enterprise_risk_score.value,
                risk_level=out.risk_level,
                priority=(
                    risk.priority.value
                    if hasattr(risk.priority, "value")
                    else str(risk.priority)
                ),
                recommended_sla=(
                    risk.recommended_sla.value
                    if hasattr(risk.recommended_sla, "value")
                    else str(risk.recommended_sla)
                ),
                business_impact=risk.business_impact.score
                if hasattr(risk.business_impact, "score")
                else None,
                technical_impact=risk.technical_impact.score
                if hasattr(risk.technical_impact, "score")
                else None,
                compliance_impact=risk.compliance_impact.score
                if hasattr(risk.compliance_impact, "score")
                else None,
                operational_impact=risk.operational_impact.score
                if hasattr(risk.operational_impact, "score")
                else None,
            ),
            owner=owner,
            asset=AssetSnapshot(
                asset_id=asset_id or finding.asset_id,
                hostname=None,
                environment=None,
                criticality=0.5,
            ),
            invoke_ai=invoke_ai,
            actor="finding-pipeline",
        )
        decision = await self._decision.decide(decision_req)
        obj = decision.decision_object
        out.decision_id = decision.id
        out.decision_action = (
            obj.decision.value if hasattr(obj.decision, "value") else str(obj.decision)
        )
        out.recommended_action = (
            obj.recommended_action.value
            if hasattr(obj.recommended_action, "value")
            else str(obj.recommended_action)
        )

        if obj.decision not in _PLAN_ACTIONS:
            out.skipped_reason = f"decision_{out.decision_action}_no_plan"
            return out

        from remediation_planner.domain.inputs import (
            AssetPlanInput,
            DecisionPlanInput,
            FindingPlanInput,
            RemediationPlanRequest,
            RiskPlanInput,
        )

        plan_req = RemediationPlanRequest(
            decision=DecisionPlanInput(
                decision_id=obj.id,
                finding_id=obj.finding_id,
                tenant_id=obj.tenant_id,
                decision=obj.decision,
                recommended_action=obj.recommended_action,
                priority=obj.priority,
                confidence=obj.confidence,
                reason=obj.reason,
                policy_version=obj.policy_version,
                owner=obj.owner,
                approver=obj.approver,
                related_policy_ids=list(obj.related_policy_ids or []),
            ),
            finding=FindingPlanInput(
                finding_id=finding.id,
                tenant_id=finding.tenant_id,
                asset_id=finding.asset_id,
                title=finding.title,
                severity=severity.value,
                finding_type=(
                    finding.finding_type.value
                    if hasattr(finding.finding_type, "value")
                    else str(finding.finding_type)
                ),
                cve_ids=list(finding.cve_ids or []),
            ),
            risk=RiskPlanInput(
                enterprise_risk_score=risk.enterprise_risk_score.value,
                risk_level=out.risk_level,
                recommended_sla=(
                    risk.recommended_sla.value
                    if hasattr(risk.recommended_sla, "value")
                    else str(risk.recommended_sla)
                ),
            ),
            asset=AssetPlanInput(asset_id=asset_id or finding.asset_id),
            actor="finding-pipeline",
        )
        plan = self._planner.plan(plan_req)
        out.plan_id = plan.id
        out.plan_summary = getattr(plan, "summary", None) or getattr(
            plan, "title", None
        )
        if out.plan_summary is None and hasattr(plan, "model_dump"):
            dumped = plan.model_dump(mode="json")
            out.plan_summary = dumped.get("summary") or dumped.get("title")
        return out

    def _load_finding(self, finding_id: UUID, tenant_id: UUID) -> SecurityFindingObject:
        return self._evidence.get_finding(finding_id, tenant_id)
