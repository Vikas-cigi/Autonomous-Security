"""ExposureRiskService — internet exposure, IOC matches, MITRE ATT&CK."""

from __future__ import annotations

from typing import List, Optional, Tuple

from risk_engine.domain.enums import FactorCategory, FactorPolarity
from risk_engine.domain.inputs import AssetRiskInput, ThreatIntelRiskInput
from risk_engine.domain.models import OperationalImpact, RiskFactor
from risk_engine.domain.weights import EXPOSURE_SUB_WEIGHTS, PILLAR_WEIGHTS


class ExposureRiskService:
    """Deterministic operational / exposure impact scoring."""

    def assess(
        self,
        asset: Optional[AssetRiskInput],
        threat_intel: Optional[ThreatIntelRiskInput],
    ) -> Tuple[OperationalImpact, List[RiskFactor]]:
        internet_facing = bool(asset and asset.internet_facing)
        ioc_count = threat_intel.ioc_match_count if threat_intel else 0
        mitre_count = threat_intel.mitre_technique_count if threat_intel else 0
        ioc_conf = threat_intel.max_ioc_confidence if threat_intel else 0.0

        internet_score = 1.0 if internet_facing else 0.15
        ioc_score = round(
            max(
                0.0,
                min(
                    1.0,
                    0.55 * min(1.0, ioc_count / 3.0) + 0.45 * ioc_conf,
                ),
            ),
            4,
        )
        mitre_score = round(min(1.0, mitre_count / 4.0), 4)

        exposure = round(
            max(
                0.0,
                min(
                    1.0,
                    EXPOSURE_SUB_WEIGHTS["internet_facing"] * internet_score
                    + EXPOSURE_SUB_WEIGHTS["ioc_matches"] * ioc_score
                    + EXPOSURE_SUB_WEIGHTS["mitre_attack"] * mitre_score,
                ),
            ),
            4,
        )

        explanation = (
            f"Operational exposure={exposure:.2f}: internet_facing={internet_facing}, "
            f"IOC matches={ioc_count}, MITRE techniques={mitre_count}."
        )
        impact = OperationalImpact(
            score=exposure,
            internet_facing=internet_facing,
            ioc_match_count=ioc_count,
            mitre_technique_count=mitre_count,
            exposure_score=exposure,
            explanation=explanation,
        )

        weight = PILLAR_WEIGHTS["exposure"]
        factors = [
            RiskFactor(
                category=FactorCategory.EXPOSURE,
                polarity=self._polarity(exposure),
                label="Operational exposure",
                description=explanation,
                raw_score=exposure,
                weight=weight,
                weighted_contribution=round(exposure * weight, 6),
            )
        ]
        if internet_facing:
            factors.append(
                RiskFactor(
                    category=FactorCategory.INTERNET_EXPOSURE,
                    polarity=FactorPolarity.ELEVATING,
                    label="Internet-facing asset",
                    description="Asset is internet-facing, increasing blast radius.",
                    raw_score=1.0,
                    weight=0.0,
                    weighted_contribution=0.0,
                )
            )
        if ioc_count > 0:
            factors.append(
                RiskFactor(
                    category=FactorCategory.IOC,
                    polarity=FactorPolarity.ELEVATING,
                    label="IOC matches",
                    description=f"{ioc_count} IOC match(es) correlated to this finding.",
                    raw_score=ioc_score,
                    weight=0.0,
                    weighted_contribution=0.0,
                )
            )
        if mitre_count > 0:
            factors.append(
                RiskFactor(
                    category=FactorCategory.MITRE,
                    polarity=FactorPolarity.ELEVATING,
                    label="MITRE ATT&CK mapping",
                    description=f"{mitre_count} MITRE technique(s) mapped.",
                    raw_score=mitre_score,
                    weight=0.0,
                    weighted_contribution=0.0,
                )
            )
        return impact, factors

    @staticmethod
    def _polarity(score: float) -> FactorPolarity:
        if score >= 0.55:
            return FactorPolarity.ELEVATING
        if score < 0.25:
            return FactorPolarity.MITIGATING
        return FactorPolarity.NEUTRAL
