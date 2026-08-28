"""DecisionService — enterprise orchestration facade."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from models.common import utc_now
from models.decision import DecisionObject
from models.enums import PolicyVerdict

from decision_service.domain.enums import (
    AuditAction,
    DecisionLifecycleStatus,
    DecisionSource,
)
from decision_service.domain.inputs import DecisionRequest
from decision_service.domain.mapping import to_decision_action
from decision_service.domain.models import (
    AIRequestEnvelope,
    AIResponseEnvelope,
    DecisionRecommendation,
    DecisionResponse,
)
from decision_service.interfaces.ai_gateway import AIDecisionGateway
from decision_service.interfaces.decision_repository import DecisionRepository
from decision_service.query.filters import DecisionSearchFilter
from decision_service.query.pagination import Page, PageRequest
from decision_service.services.audit_service import DecisionAuditService
from decision_service.services.context_assembler import DecisionContextAssembler
from decision_service.services.deterministic_advisor import DeterministicDecisionAdvisor
from decision_service.services.explanation_service import DecisionExplanationService
from decision_service.services.recommendation_parser import DecisionRecommendationParser
from decision_service.services.validation_service import DecisionValidationService

logger = logging.getLogger(__name__)

ALGORITHM_VERSION = "1.0.0"


class DecisionService:
    """
    Orchestrate intelligence → AI (optional) → policy → DecisionObject.

    Pipeline position: after Risk Engine, before Remediation Planner.
    Does not re-implement Trust/Risk/TI/Evidence scoring or scanner I/O.
    """

    def __init__(
        self,
        decision_repository: DecisionRepository,
        *,
        audit_service: Optional[DecisionAuditService] = None,
        context_assembler: Optional[DecisionContextAssembler] = None,
        validation_service: Optional[DecisionValidationService] = None,
        explanation_service: Optional[DecisionExplanationService] = None,
        deterministic_advisor: Optional[DeterministicDecisionAdvisor] = None,
        recommendation_parser: Optional[DecisionRecommendationParser] = None,
        ai_gateway: Optional[AIDecisionGateway] = None,
    ) -> None:
        self._repo = decision_repository
        self._audit = audit_service
        self._assembler = context_assembler or DecisionContextAssembler()
        self._validation = validation_service or DecisionValidationService()
        self._explanation = explanation_service or DecisionExplanationService()
        self._deterministic = deterministic_advisor or DeterministicDecisionAdvisor()
        self._parser = recommendation_parser or DecisionRecommendationParser()
        self._ai_gateway = ai_gateway

    async def decide(
        self,
        request: DecisionRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        decision_id: Optional[UUID] = None,
    ) -> DecisionResponse:
        """Run full orchestration and optionally persist the DecisionResponse."""

        self._validation.validate_request(request)
        actor = actor or request.actor

        if self._audit is not None:
            self._audit.record(
                action=AuditAction.REQUEST_RECEIVED,
                message="Decision request received",
                tenant_id=request.finding.tenant_id,
                finding_id=request.finding.finding_id,
                actor=actor,
            )

        context = self._assembler.assemble(request)
        if self._audit is not None:
            self._audit.record(
                action=AuditAction.CONTEXT_ASSEMBLED,
                message="Decision context assembled",
                tenant_id=context.tenant_id,
                finding_id=context.finding_id,
                actor=actor,
                details={"key_signals": context.reasoning.key_signals},
            )

        ai_request: Optional[AIRequestEnvelope] = None
        ai_response: Optional[AIResponseEnvelope] = None
        recommendation: DecisionRecommendation

        if request.invoke_ai and self._ai_gateway is not None:
            ai_request, ai_response = await self._ai_gateway.invoke(
                context,
                session_id=request.session_id,
                provider_name=request.provider_name,
            )
            if self._audit is not None:
                self._audit.record(
                    action=AuditAction.AI_INVOKED,
                    message="AI stack invoked",
                    tenant_id=context.tenant_id,
                    finding_id=context.finding_id,
                    actor=actor,
                    details={
                        "provider": ai_response.provider,
                        "model": ai_response.model,
                        "latency_ms": ai_response.latency_ms,
                    },
                )
            parsed = self._parser.parse(
                ai_response,
                context,
                preferred_action=request.preferred_action,
            )
            if parsed is not None:
                recommendation = parsed
                if self._audit is not None:
                    self._audit.record(
                        action=AuditAction.AI_PARSED,
                        message="AI recommendation parsed",
                        tenant_id=context.tenant_id,
                        finding_id=context.finding_id,
                        actor=actor,
                        decision_type=recommendation.decision_type.value,
                        confidence=recommendation.confidence,
                    )
            else:
                recommendation = self._deterministic.recommend(
                    context,
                    preferred_action=request.preferred_action,
                )
                recommendation = recommendation.model_copy(
                    update={
                        "source": DecisionSource.HYBRID,
                        "raw_ai_text": ai_response.text[:16000] if ai_response else None,
                    }
                )
                if self._audit is not None:
                    self._audit.record(
                        action=AuditAction.DETERMINISTIC_FALLBACK,
                        message="AI parse failed; deterministic fallback used",
                        tenant_id=context.tenant_id,
                        finding_id=context.finding_id,
                        actor=actor,
                        decision_type=recommendation.decision_type.value,
                        confidence=recommendation.confidence,
                    )
        else:
            recommendation = self._deterministic.recommend(
                context,
                preferred_action=request.preferred_action,
            )
            if self._audit is not None:
                self._audit.record(
                    action=AuditAction.DETERMINISTIC_FALLBACK,
                    message="Deterministic advisor used (AI not invoked)",
                    tenant_id=context.tenant_id,
                    finding_id=context.finding_id,
                    actor=actor,
                    decision_type=recommendation.decision_type.value,
                    confidence=recommendation.confidence,
                )

        recommendation, approver = self._validation.ensure_approval_rules(
            recommendation,
            owner=request.owner,
            approver=request.approver,
        )

        policy_decision = self._validation.evaluate_policy(request, recommendation)
        if self._audit is not None:
            self._audit.record(
                action=AuditAction.POLICY_EVALUATED,
                message=f"Policy verdict={policy_decision.verdict.value}",
                tenant_id=context.tenant_id,
                finding_id=context.finding_id,
                actor=actor,
                details={
                    "verdict": policy_decision.verdict.value,
                    "reason": policy_decision.reason,
                    "evaluator": policy_decision.evaluator,
                },
            )

        status = DecisionLifecycleStatus.PROPOSED
        if policy_decision.verdict == PolicyVerdict.DENY:
            status = DecisionLifecycleStatus.POLICY_DENIED
            # Soft-fail path: still emit envelope for audit; callers may raise.
            logger.warning(
                "Decision policy denied finding=%s reason=%s",
                context.finding_id,
                policy_decision.reason,
            )
        elif policy_decision.verdict == PolicyVerdict.ESCALATE:
            status = DecisionLifecycleStatus.POLICY_ESCALATED
            if recommendation.decision_type.value != "escalate":
                from decision_service.domain.enums import SecurityDecisionType
                from decision_service.domain.mapping import to_recommended_action

                recommendation = recommendation.model_copy(
                    update={
                        "decision_type": SecurityDecisionType.ESCALATE,
                        "recommended_action": to_recommended_action(
                            SecurityDecisionType.ESCALATE
                        ),
                        "next_step": (
                            "Policy requires escalation/approval before proceeding. "
                            + recommendation.next_step
                        )[:2000],
                    }
                )
        else:
            status = DecisionLifecycleStatus.FINALIZED

        explanation = self._explanation.explain(
            context,
            recommendation,
            ai_explanation=(
                ai_response.text
                if ai_response and recommendation.source in {
                    DecisionSource.AI,
                    DecisionSource.HYBRID,
                }
                else None
            ),
        )

        decision_object = DecisionObject(
            finding_id=context.finding_id,
            tenant_id=context.tenant_id,
            decision=to_decision_action(recommendation.decision_type),
            reason=explanation.summary,
            confidence=recommendation.confidence,
            recommended_action=recommendation.recommended_action,
            priority=recommendation.priority,
            policy_version=request.policy.policy_version,
            owner=request.owner,
            approver=approver,
            decided_at=request.evaluated_at or utc_now(),
            related_policy_ids=list(
                policy_decision.matched_rule_ids or request.policy.related_policy_ids
            ),
        )

        now = request.evaluated_at or utc_now()
        kwargs = {
            "tenant_id": context.tenant_id,
            "finding_id": context.finding_id,
            "asset_id": context.asset_id,
            "status": status,
            "decision_object": decision_object,
            "recommendation": recommendation,
            "explanation": explanation,
            "context": context,
            "ai_request": ai_request,
            "ai_response": ai_response,
            "policy_verdict": policy_decision.verdict.value,
            "policy_reason": policy_decision.reason,
            "algorithm_version": ALGORITHM_VERSION,
            "decided_at": now,
            "first_decided_at": now,
            "last_decided_at": now,
        }
        if decision_id is not None:
            kwargs["id"] = decision_id
        response = DecisionResponse(**kwargs)

        if persist:
            response = self._repo.save(
                response,
                actor=actor,
                change_summary="Enterprise decision computed",
            )
            if self._audit is not None:
                self._audit.record(
                    action=AuditAction.DECISION_FINALIZED
                    if status == DecisionLifecycleStatus.FINALIZED
                    else AuditAction.DECISION_CREATED,
                    message=f"Decision persisted status={status.value}",
                    tenant_id=response.tenant_id,
                    finding_id=response.finding_id,
                    decision_id=response.id,
                    actor=actor,
                    decision_type=recommendation.decision_type.value,
                    confidence=recommendation.confidence,
                )

        return response

    def get_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[DecisionResponse]:
        return self._repo.find_by_finding(finding_id, tenant_id)

    def get_decision(
        self,
        decision_id: UUID,
        tenant_id: UUID,
    ) -> DecisionResponse:
        return self._repo.get(decision_id, tenant_id)

    def search(
        self,
        filters: DecisionSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[DecisionResponse]:
        return self._repo.search(filters, page or PageRequest())
