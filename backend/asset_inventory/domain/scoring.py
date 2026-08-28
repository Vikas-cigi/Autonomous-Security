"""Criticality scoring for inventory assets."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from models.common import FortiBaseModel
from asset_inventory.domain.classification import AssetClassification
from asset_inventory.domain.enums import (
    CriticalityTier,
    DataSensitivity,
    EnvironmentKind,
    ExposureLevel,
)


_TIER_WEIGHT: dict[CriticalityTier, float] = {
    CriticalityTier.INFORMATIONAL: 0.1,
    CriticalityTier.LOW: 0.25,
    CriticalityTier.MEDIUM: 0.5,
    CriticalityTier.HIGH: 0.75,
    CriticalityTier.CRITICAL: 1.0,
}

_SENSITIVITY_WEIGHT: dict[DataSensitivity, float] = {
    DataSensitivity.UNKNOWN: 0.3,
    DataSensitivity.PUBLIC: 0.15,
    DataSensitivity.INTERNAL: 0.4,
    DataSensitivity.CONFIDENTIAL: 0.75,
    DataSensitivity.RESTRICTED: 1.0,
}

_EXPOSURE_WEIGHT: dict[ExposureLevel, float] = {
    ExposureLevel.ISOLATED: 0.05,
    ExposureLevel.PRIVATE: 0.2,
    ExposureLevel.CORPORATE: 0.4,
    ExposureLevel.PARTNER: 0.65,
    ExposureLevel.PUBLIC_INTERNET: 1.0,
    ExposureLevel.UNKNOWN: 0.35,
}

_ENV_WEIGHT: dict[EnvironmentKind, float] = {
    EnvironmentKind.SANDBOX: 0.1,
    EnvironmentKind.TEST: 0.15,
    EnvironmentKind.DEVELOPMENT: 0.2,
    EnvironmentKind.STAGING: 0.45,
    EnvironmentKind.DR: 0.7,
    EnvironmentKind.PRODUCTION: 1.0,
    EnvironmentKind.OTHER: 0.35,
}


class CriticalityScore(FortiBaseModel):
    """Computed criticality score with explainable components."""

    score: float = Field(..., ge=0.0, le=1.0)
    tier: CriticalityTier
    business_component: float = Field(..., ge=0.0, le=1.0)
    sensitivity_component: float = Field(..., ge=0.0, le=1.0)
    exposure_component: float = Field(..., ge=0.0, le=1.0)
    environment_component: float = Field(..., ge=0.0, le=1.0)
    compliance_boost: float = Field(..., ge=0.0, le=0.2)
    crown_jewel_boost: float = Field(..., ge=0.0, le=0.25)


class CriticalityScorer:
    """
    Deterministic criticality scoring.

    Weights are fixed for reproducibility across tenants; override via
    subclassing if product policy needs different curves.
    """

    def score(
        self,
        classification: AssetClassification,
        *,
        environment_kind: Optional[EnvironmentKind] = None,
    ) -> CriticalityScore:
        """Compute a normalized score and mapped tier."""

        business = _TIER_WEIGHT[classification.business_criticality]
        sensitivity = _SENSITIVITY_WEIGHT[classification.data_sensitivity]
        exposure = _EXPOSURE_WEIGHT[classification.internet_exposure.level]
        env = _ENV_WEIGHT.get(environment_kind or EnvironmentKind.OTHER, 0.35)

        compliance_boost = 0.0
        if classification.regulated or classification.compliance_tags:
            compliance_boost = min(0.2, 0.05 + 0.03 * len(classification.compliance_tags))

        crown = 0.25 if classification.crown_jewel else 0.0

        raw = (
            0.30 * business
            + 0.25 * sensitivity
            + 0.25 * exposure
            + 0.20 * env
            + compliance_boost
            + crown
        )
        score = max(0.0, min(1.0, raw))
        return CriticalityScore(
            score=round(score, 4),
            tier=self._tier_for(score, classification),
            business_component=business,
            sensitivity_component=sensitivity,
            exposure_component=exposure,
            environment_component=env,
            compliance_boost=compliance_boost,
            crown_jewel_boost=crown,
        )

    @staticmethod
    def _tier_for(
        score: float,
        classification: AssetClassification,
    ) -> CriticalityTier:
        if classification.crown_jewel:
            return CriticalityTier.CRITICAL
        if score >= 0.85:
            return CriticalityTier.CRITICAL
        if score >= 0.65:
            return CriticalityTier.HIGH
        if score >= 0.40:
            return CriticalityTier.MEDIUM
        if score >= 0.20:
            return CriticalityTier.LOW
        return CriticalityTier.INFORMATIONAL
