"""
Enterprise Risk Engine.

Calculates the Enterprise Risk Score for every SecurityFindingObject after
Trust Scoring and before the Decision Service. Produces a deterministic
RiskAssessment joined by finding_id + tenant_id.

Consumes snapshots from Evidence Repository, Asset Inventory, Threat
Intelligence, and Trust Scoring. Does not modify existing platform modules.
No REST APIs. No AI/LLM — scoring is fully reproducible from the same inputs.
"""

from risk_engine.di.container import RiskEngineContainer, RiskEngineServices
from risk_engine.domain.builders import build_risk_scoring_input
from risk_engine.domain.enums import (
    BusinessContext,
    ComplianceFramework,
    RecommendedSLA,
    RiskLevel,
    RiskPriority,
)
from risk_engine.domain.history import RiskAuditRecord, RiskHistory
from risk_engine.domain.inputs import RiskScoringInput
from risk_engine.domain.models import (
    BusinessImpact,
    ComplianceImpact,
    EnterpriseRiskScore,
    OperationalImpact,
    RiskAssessment,
    RiskExplanation,
    RiskFactor,
    TechnicalImpact,
)
from risk_engine.interfaces.risk_history_repository import RiskHistoryRepository
from risk_engine.interfaces.risk_repository import RiskRepository
from risk_engine.services.risk_engine_service import RiskEngineService

__all__ = [
    "BusinessContext",
    "BusinessImpact",
    "ComplianceFramework",
    "ComplianceImpact",
    "EnterpriseRiskScore",
    "OperationalImpact",
    "RecommendedSLA",
    "RiskAssessment",
    "RiskAuditRecord",
    "RiskEngineContainer",
    "RiskEngineService",
    "RiskEngineServices",
    "RiskExplanation",
    "RiskFactor",
    "RiskHistory",
    "RiskHistoryRepository",
    "RiskLevel",
    "RiskPriority",
    "RiskRepository",
    "RiskScoringInput",
    "TechnicalImpact",
    "build_risk_scoring_input",
]

__version__ = "1.0.0"
