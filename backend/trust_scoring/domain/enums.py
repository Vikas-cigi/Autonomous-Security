"""Domain enums for the Enterprise Trust Scoring Engine."""

from __future__ import annotations

from enum import Enum


class TrustLevel(str, Enum):
    """Normalized trust / confidence level for a finding."""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class FactorPolarity(str, Enum):
    """Whether a confidence factor supports or undermines trust."""

    SUPPORTING = "supporting"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class FactorCategory(str, Enum):
    """Taxonomy of confidence factor sources."""

    EVIDENCE_QUALITY = "evidence_quality"
    SCANNER_CONFIDENCE = "scanner_confidence"
    CROSS_VALIDATION = "cross_validation"
    HISTORICAL_RELIABILITY = "historical_reliability"
    FINDING_CORRELATION = "finding_correlation"
    ASSET_CONFIDENCE = "asset_confidence"
    THREAT_INTELLIGENCE = "threat_intelligence"
    IOC_CONFIDENCE = "ioc_confidence"
    DUPLICATE_FINDING = "duplicate_finding"
    CONSISTENCY = "consistency"
    TIME_DECAY = "time_decay"
    FINDING_BASELINE = "finding_baseline"


class EvidenceQualityTier(str, Enum):
    """Discrete evidence quality assessment."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class CrossValidationStatus(str, Enum):
    """Outcome of multi-scanner cross-validation."""

    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    SINGLE_SOURCE = "single_source"
    CONFLICTING = "conflicting"
    INCONCLUSIVE = "inconclusive"


class RecommendationConfidence(str, Enum):
    """Confidence that remediation recommendations based on this finding are sound."""

    ACT = "act"
    INVESTIGATE = "investigate"
    DEFER = "defer"
    DISCARD = "discard"


class AuditAction(str, Enum):
    """Audit actions for Trust Scoring operations."""

    ASSESSMENT_CREATED = "assessment_created"
    ASSESSMENT_UPDATED = "assessment_updated"
    ASSESSMENT_SCORED = "assessment_scored"
    FACTOR_RECORDED = "factor_recorded"
    HISTORY_RECORDED = "history_recorded"
    SEARCHED = "searched"
    DECAY_APPLIED = "decay_applied"
