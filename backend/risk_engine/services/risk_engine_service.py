"""RiskEngineService — facade orchestrating deterministic enterprise risk."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from models.common import utc_now
from risk_engine.domain.enums import AuditAction
from risk_engine.domain.inputs import RiskScoringInput
from risk_engine.domain.models import RiskAssessment
from risk_engine.domain.weights import (
    ALGORITHM_VERSION,
    priority_for_level,
    sla_for_level,
)
from risk_engine.exceptions import InvalidRiskInputError
from risk_engine.interfaces.risk_history_repository import RiskHistoryRepository
from risk_engine.interfaces.risk_repository import RiskRepository
from risk_engine.query.filters import RiskAssessmentSearchFilter
from risk_engine.query.pagination import Page, PageRequest
from risk_engine.services.audit import AuditLogger
from risk_engine.services.business_risk import BusinessRiskService
from risk_engine.services.compliance_risk import ComplianceRiskService
from risk_engine.services.exposure_risk import ExposureRiskService
from risk_engine.services.risk_aggregation import RiskAggregationService
from risk_engine.services.technical_risk import TechnicalRiskService


class RiskEngineService:
    """
    Evaluate and persist RiskAssessment for a SecurityFindingObject.

    Pipeline position: after Trust Scoring, before Decision Service.
    Deterministic: identical RiskScoringInput always yields the same score
    components (factor/assessment UUIDs may differ unless provided).
    No AI, LLM, or external API calls.
    """

    def __init__(
        self,
        risk_repository: RiskRepository,
        *,
        history_repository: Optional[RiskHistoryRepository] = None,
        technical_service: Optional[TechnicalRiskService] = None,
        business_service: Optional[BusinessRiskService] = None,
        compliance_service: Optional[ComplianceRiskService] = None,
        exposure_service: Optional[ExposureRiskService] = None,
        aggregation_service: Optional[RiskAggregationService] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._risk_repo = risk_repository
        self._history_repo = history_repository
        self._technical = technical_service or TechnicalRiskService()
        self._business = business_service or BusinessRiskService()
        self._compliance = compliance_service or ComplianceRiskService()
        self._exposure = exposure_service or ExposureRiskService()
        self._aggregation = aggregation_service or RiskAggregationService()
        self._audit = audit_logger

    def score(
        self,
        scoring_input: RiskScoringInput,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        assessment_id: Optional[UUID] = None,
    ) -> RiskAssessment:
        """Compute (and optionally persist) a RiskAssessment."""

        self._validate_input(scoring_input)
        assessment = self.compute(scoring_input, assessment_id=assessment_id)

        if persist:
            assessment = self._risk_repo.save_assessment(
                assessment,
                actor=actor,
                change_summary="Enterprise risk score computed",
            )
            if self._audit is not None:
                self._audit.log(
                    tenant_id=assessment.tenant_id,
                    action=AuditAction.ASSESSMENT_SCORED,
                    message=(
                        f"Scored finding {assessment.finding_id} "
                        f"at {assessment.enterprise_risk_score.value}"
                    ),
                    actor=actor,
                    details={
                        "assessment_id": str(assessment.id),
                        "score": assessment.enterprise_risk_score.value,
                        "level": assessment.risk_level.value,
                        "priority": assessment.priority.value,
                        "recommended_sla": assessment.recommended_sla.value,
                        "algorithm_version": assessment.algorithm_version,
                    },
                )
        return assessment

    def compute(
        self,
        scoring_input: RiskScoringInput,
        *,
        assessment_id: Optional[UUID] = None,
    ) -> RiskAssessment:
        """Pure computation — no persistence. Fully deterministic given inputs."""

        finding = scoring_input.finding
        factors = []

        technical_impact, tech_factors = self._technical.assess(
            finding,
            scoring_input.cvss,
            scoring_input.threat_intel,
        )
        factors.extend(tech_factors)

        business_impact, biz_factors = self._business.assess(scoring_input.asset)
        factors.extend(biz_factors)

        compliance_impact, comp_factors = self._compliance.assess(scoring_input.asset)
        factors.extend(comp_factors)

        operational_impact, exp_factors = self._exposure.assess(
            scoring_input.asset,
            scoring_input.threat_intel,
        )
        factors.extend(exp_factors)

        _, trust_factor = self._aggregation.trust_factor(scoring_input.trust)
        factors.append(trust_factor)

        hist_factor = self._aggregation.historical_factor(
            scoring_input.historical,
            apply=scoring_input.apply_historical_blend,
        )
        if hist_factor is not None:
            factors.append(hist_factor)

        risk_score = self._aggregation.aggregate(
            factors,
            historical=scoring_input.historical,
            apply_historical_blend=scoring_input.apply_historical_blend,
        )
        explanation = self._aggregation.build_explanation(risk_score, factors)

        now = finding.evaluated_at or utc_now()
        kwargs = {
            "tenant_id": finding.tenant_id,
            "finding_id": finding.finding_id,
            "asset_id": finding.asset_id,
            "enterprise_risk_score": risk_score,
            "risk_level": risk_score.level,
            "priority": priority_for_level(risk_score.level),
            "recommended_sla": sla_for_level(risk_score.level),
            "factors": factors,
            "business_impact": business_impact,
            "technical_impact": technical_impact,
            "compliance_impact": compliance_impact,
            "operational_impact": operational_impact,
            "explanation": explanation,
            "trust_score_used": scoring_input.trust.trust_score,
            "scored_at": now,
            "algorithm_version": ALGORITHM_VERSION,
            "first_scored_at": now,
            "last_scored_at": now,
        }
        if assessment_id is not None:
            kwargs["id"] = assessment_id
        return RiskAssessment(**kwargs)

    def get_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[RiskAssessment]:
        return self._risk_repo.find_by_finding(finding_id, tenant_id)

    def get_assessment(
        self,
        assessment_id: UUID,
        tenant_id: UUID,
    ) -> RiskAssessment:
        return self._risk_repo.get_assessment(assessment_id, tenant_id)

    def search(
        self,
        filters: RiskAssessmentSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[RiskAssessment]:
        return self._risk_repo.search_assessments(
            filters,
            page or PageRequest(),
        )

    @staticmethod
    def _validate_input(scoring_input: RiskScoringInput) -> None:
        finding = scoring_input.finding
        if scoring_input.asset is not None and scoring_input.asset.asset_id != finding.asset_id:
            raise InvalidRiskInputError(
                "asset.asset_id must match finding.asset_id",
                details={
                    "finding_asset_id": str(finding.asset_id),
                    "asset_id": str(scoring_input.asset.asset_id),
                },
            )
