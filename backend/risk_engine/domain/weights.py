"""Fixed, deterministic scoring weights for the Enterprise Risk Engine."""

from __future__ import annotations

from typing import Dict

from risk_engine.domain.enums import (
    BusinessContext,
    ComplianceFramework,
    RecommendedSLA,
    RiskLevel,
    RiskPriority,
)


PILLAR_WEIGHTS: Dict[str, float] = {
    "technical": 0.30,
    "business": 0.25,
    "compliance": 0.15,
    "exposure": 0.15,
    "trust": 0.15,
}

TECHNICAL_SUB_WEIGHTS: Dict[str, float] = {
    "cvss": 0.35,
    "epss": 0.20,
    "active_exploitation": 0.20,
    "kev": 0.15,
    "finding_age": 0.10,
}

BUSINESS_SUB_WEIGHTS: Dict[str, float] = {
    "asset_criticality": 0.35,
    "business_criticality": 0.30,
    "environment": 0.20,
    "customer_facing": 0.15,
}

EXPOSURE_SUB_WEIGHTS: Dict[str, float] = {
    "internet_facing": 0.40,
    "ioc_matches": 0.35,
    "mitre_attack": 0.25,
}

COMPLIANCE_FRAMEWORK_WEIGHTS: Dict[ComplianceFramework, float] = {
    ComplianceFramework.PCI: 1.00,
    ComplianceFramework.HIPAA: 0.95,
    ComplianceFramework.GDPR: 0.90,
    ComplianceFramework.SOC2: 0.80,
    ComplianceFramework.ISO27001: 0.75,
    ComplianceFramework.NIST: 0.70,
    ComplianceFramework.CIS: 0.60,
}

ENVIRONMENT_SCORES: Dict[BusinessContext, float] = {
    BusinessContext.PRODUCTION: 1.00,
    BusinessContext.CUSTOMER_FACING: 0.95,
    BusinessContext.INTERNET_FACING: 0.90,
    BusinessContext.STAGING: 0.45,
    BusinessContext.INTERNAL: 0.40,
    BusinessContext.DEVELOPMENT: 0.25,
}

RISK_LEVEL_THRESHOLDS: tuple[tuple[float, RiskLevel], ...] = (
    (90.0, RiskLevel.CRITICAL),
    (70.0, RiskLevel.HIGH),
    (40.0, RiskLevel.MEDIUM),
    (20.0, RiskLevel.LOW),
    (0.0, RiskLevel.INFORMATIONAL),
)

SLA_FOR_LEVEL: Dict[RiskLevel, RecommendedSLA] = {
    RiskLevel.CRITICAL: RecommendedSLA.IMMEDIATE,
    RiskLevel.HIGH: RecommendedSLA.HOURS_24,
    RiskLevel.MEDIUM: RecommendedSLA.DAYS_7,
    RiskLevel.LOW: RecommendedSLA.DAYS_30,
    RiskLevel.INFORMATIONAL: RecommendedSLA.MONITOR,
}

PRIORITY_FOR_LEVEL: Dict[RiskLevel, RiskPriority] = {
    RiskLevel.CRITICAL: RiskPriority.P1,
    RiskLevel.HIGH: RiskPriority.P2,
    RiskLevel.MEDIUM: RiskPriority.P3,
    RiskLevel.LOW: RiskPriority.P4,
    RiskLevel.INFORMATIONAL: RiskPriority.P5,
}

HISTORICAL_BLEND_WEIGHT: float = 0.10
ALGORITHM_VERSION = "1.0.0"


def risk_level_for_score(score: float) -> RiskLevel:
    clamped = max(0.0, min(100.0, score))
    for threshold, level in RISK_LEVEL_THRESHOLDS:
        if clamped >= threshold:
            return level
    return RiskLevel.INFORMATIONAL


def sla_for_level(level: RiskLevel) -> RecommendedSLA:
    return SLA_FOR_LEVEL[level]


def priority_for_level(level: RiskLevel) -> RiskPriority:
    return PRIORITY_FOR_LEVEL[level]


def assert_weights_sum() -> None:
    for name, weights in (
        ("PILLAR_WEIGHTS", PILLAR_WEIGHTS),
        ("TECHNICAL_SUB_WEIGHTS", TECHNICAL_SUB_WEIGHTS),
        ("BUSINESS_SUB_WEIGHTS", BUSINESS_SUB_WEIGHTS),
        ("EXPOSURE_SUB_WEIGHTS", EXPOSURE_SUB_WEIGHTS),
    ):
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-9:
            raise RuntimeError(f"{name} must sum to 1.0, got {total}")


assert_weights_sum()
