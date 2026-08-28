"""
Enterprise Trust Scoring Engine.

Evaluates confidence and reliability of every SecurityFindingObject before
it reaches the Risk Engine. Produces a deterministic TrustAssessment joined
by finding_id + tenant_id.

Does not modify existing platform modules. No REST APIs. No AI/LLM or
external API calls — scoring is fully reproducible from the same inputs.
"""

from trust_scoring.di.container import TrustScoringContainer, TrustScoringServices
from trust_scoring.domain.enums import (
    RecommendationConfidence,
    TrustLevel,
)
from trust_scoring.domain.history import TrustAssessmentVersion, TrustAuditRecord
from trust_scoring.domain.inputs import TrustScoringInput
from trust_scoring.domain.builders import build_scoring_input
from trust_scoring.domain.models import (
    ConfidenceFactor,
    CrossValidationResult,
    EvidenceQuality,
    FindingCorrelation,
    HistoricalReliability,
    ScannerConfidence,
    TrustAssessment,
    TrustScore,
)
from trust_scoring.interfaces.confidence_repository import ConfidenceRepository
from trust_scoring.interfaces.trust_history_repository import TrustHistoryRepository
from trust_scoring.interfaces.trust_repository import TrustRepository
from trust_scoring.services.trust_scoring_service import TrustScoringService

__all__ = [
    "ConfidenceFactor",
    "ConfidenceRepository",
    "CrossValidationResult",
    "EvidenceQuality",
    "FindingCorrelation",
    "HistoricalReliability",
    "RecommendationConfidence",
    "ScannerConfidence",
    "TrustAssessment",
    "TrustAssessmentVersion",
    "TrustAuditRecord",
    "TrustHistoryRepository",
    "TrustLevel",
    "TrustRepository",
    "TrustScore",
    "TrustScoringContainer",
    "TrustScoringInput",
    "TrustScoringService",
    "TrustScoringServices",
    "build_scoring_input",
]

__version__ = "1.0.0"
