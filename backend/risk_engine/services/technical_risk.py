"""TechnicalRiskService — CVSS, EPSS, exploitation, KEV, finding age."""

from __future__ import annotations

from typing import List, Optional, Tuple

from risk_engine.domain.enums import FactorCategory, FactorPolarity
from risk_engine.domain.inputs import (
    CvssInput,
    FindingRiskBaselineInput,
    ThreatIntelRiskInput,
)
from risk_engine.domain.models import RiskFactor, TechnicalImpact
from risk_engine.domain.weights import PILLAR_WEIGHTS, TECHNICAL_SUB_WEIGHTS


class TechnicalRiskService:
    """Deterministic technical impact scoring."""

    def assess(
        self,
        finding: FindingRiskBaselineInput,
        cvss: Optional[CvssInput],
        threat_intel: Optional[ThreatIntelRiskInput],
    ) -> Tuple[TechnicalImpact, List[RiskFactor]]:
        cvss_norm = self._cvss_normalized(finding, cvss)
        epss = (
            threat_intel.epss_score
            if threat_intel and threat_intel.epss_score is not None
            else 0.0
        )
        actively_exploited = bool(
            threat_intel and threat_intel.actively_exploited
        )
        in_kev = bool(threat_intel and threat_intel.in_cisa_kev)
        age_factor = self._age_factor(finding.finding_age_days)

        exploit_score = 1.0 if actively_exploited else 0.0
        kev_score = 1.0 if in_kev else 0.0

        score = round(
            max(
                0.0,
                min(
                    1.0,
                    TECHNICAL_SUB_WEIGHTS["cvss"] * cvss_norm
                    + TECHNICAL_SUB_WEIGHTS["epss"] * epss
                    + TECHNICAL_SUB_WEIGHTS["active_exploitation"] * exploit_score
                    + TECHNICAL_SUB_WEIGHTS["kev"] * kev_score
                    + TECHNICAL_SUB_WEIGHTS["finding_age"] * age_factor,
                ),
            ),
            4,
        )

        explanation = (
            f"Technical impact={score:.2f}: CVSS_norm={cvss_norm:.2f}, "
            f"EPSS={epss:.2f}, actively_exploited={actively_exploited}, "
            f"CISA_KEV={in_kev}, age_factor={age_factor:.2f}."
        )
        impact = TechnicalImpact(
            score=score,
            cvss_normalized=cvss_norm,
            epss_score=epss,
            actively_exploited=actively_exploited,
            in_cisa_kev=in_kev,
            finding_age_factor=age_factor,
            explanation=explanation,
        )

        weight = PILLAR_WEIGHTS["technical"]
        factors = [
            RiskFactor(
                category=FactorCategory.TECHNICAL,
                polarity=self._polarity(score),
                label="Technical impact",
                description=explanation,
                raw_score=score,
                weight=weight,
                weighted_contribution=round(score * weight, 6),
            )
        ]
        if in_kev:
            factors.append(
                RiskFactor(
                    category=FactorCategory.KEV,
                    polarity=FactorPolarity.ELEVATING,
                    label="CISA KEV listing",
                    description="Finding maps to a CISA Known Exploited Vulnerability.",
                    raw_score=1.0,
                    weight=0.0,
                    weighted_contribution=0.0,
                )
            )
        if actively_exploited:
            factors.append(
                RiskFactor(
                    category=FactorCategory.ACTIVE_EXPLOITATION,
                    polarity=FactorPolarity.ELEVATING,
                    label="Active exploitation",
                    description="Threat intelligence indicates active exploitation.",
                    raw_score=1.0,
                    weight=0.0,
                    weighted_contribution=0.0,
                )
            )
        return impact, factors

    @staticmethod
    def _cvss_normalized(
        finding: FindingRiskBaselineInput,
        cvss: Optional[CvssInput],
    ) -> float:
        if cvss and cvss.base_score is not None:
            return round(max(0.0, min(1.0, cvss.base_score / 10.0)), 4)
        if finding.severity_hint is not None:
            return round(max(0.0, min(1.0, finding.severity_hint / 10.0)), 4)
        return 0.35

    @staticmethod
    def _age_factor(age_days: float) -> float:
        # Older open findings increase urgency up to a soft cap at ~180 days.
        if age_days <= 0:
            return 0.0
        return round(max(0.0, min(1.0, age_days / 180.0)), 4)

    @staticmethod
    def _polarity(score: float) -> FactorPolarity:
        if score >= 0.55:
            return FactorPolarity.ELEVATING
        if score < 0.30:
            return FactorPolarity.MITIGATING
        return FactorPolarity.NEUTRAL
