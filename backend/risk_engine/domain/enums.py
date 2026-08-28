"""Domain enums for the Enterprise Risk Engine."""

from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    """Enterprise risk category derived from the 0-100 score."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RiskPriority(str, Enum):
    """Operational priority for remediation work."""

    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"
    P5 = "p5"


class RecommendedSLA(str, Enum):
    """Deterministic SLA recommendation mapped from RiskLevel."""

    IMMEDIATE = "immediate"
    HOURS_24 = "24_hours"
    DAYS_7 = "7_days"
    DAYS_30 = "30_days"
    MONITOR = "monitor"


class FactorPolarity(str, Enum):
    """Whether a risk factor elevates or reduces risk."""

    ELEVATING = "elevating"
    MITIGATING = "mitigating"
    NEUTRAL = "neutral"


class FactorCategory(str, Enum):
    """Taxonomy of risk factor sources."""

    TECHNICAL = "technical"
    BUSINESS = "business"
    COMPLIANCE = "compliance"
    EXPOSURE = "exposure"
    TRUST = "trust"
    THREAT_INTELLIGENCE = "threat_intelligence"
    HISTORICAL = "historical"
    FINDING_AGE = "finding_age"
    CVSS = "cvss"
    EPSS = "epss"
    KEV = "kev"
    ACTIVE_EXPLOITATION = "active_exploitation"
    IOC = "ioc"
    MITRE = "mitre"
    ASSET_CRITICALITY = "asset_criticality"
    INTERNET_EXPOSURE = "internet_exposure"


class BusinessContext(str, Enum):
    """Business / deployment context for the asset or finding."""

    PRODUCTION = "production"
    DEVELOPMENT = "development"
    STAGING = "staging"
    INTERNAL = "internal"
    INTERNET_FACING = "internet_facing"
    CUSTOMER_FACING = "customer_facing"


class ComplianceFramework(str, Enum):
    """Compliance regimes that elevate remediation urgency."""

    PCI = "pci"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    GDPR = "gdpr"
    NIST = "nist"
    CIS = "cis"


class AuditAction(str, Enum):
    """Audit actions for Risk Engine operations."""

    ASSESSMENT_CREATED = "assessment_created"
    ASSESSMENT_UPDATED = "assessment_updated"
    ASSESSMENT_SCORED = "assessment_scored"
    HISTORY_RECORDED = "history_recorded"
    SEARCHED = "searched"
    FACTOR_RECORDED = "factor_recorded"
