"""
Forti-ai canonical security domain models.

These types are the single source of truth for findings, evidence, decisions,
policies, remediations, simulations, verification, and outcomes.

AI framework packages (decision_engine, context, prompt, providers) are
intentionally separate and untouched.
"""

from models.common import ActorReference, MetadataBag
from models.decision import DecisionObject
from models.enums import (
    ApprovalStatus,
    BusinessImpact,
    DecisionAction,
    EvidenceSource,
    EvidenceValidationStatus,
    ExecutionStatus,
    Exploitability,
    FindingStatus,
    FindingType,
    HashAlgorithm,
    OutcomeStatus,
    ActionClass,
    PolicyEffect,
    PolicyScope,
    PolicyVerdict,
    Priority,
    RecommendedAction,
    Severity,
    SimulationStatus,
    SourceTool,
    VerificationStatus,
)
from models.evidence import ContentHash, EvidenceLineage, EvidenceObject
from models.outcome import OutcomeMetrics, OutcomeObject
from models.policy import PolicyCondition, PolicyObject, PolicyRule
from models.remediation import (
    ApprovalRecord,
    RemediationObject,
    RemediationPlan,
    RemediationStep,
    RollbackPlan,
)
from models.security_finding import SecurityFindingObject
from models.simulation import SimulationImpact, SimulationObject
from models.verification import VerificationCheck, VerificationObject

__all__ = [
    "ActionClass",
    "ActorReference",
    "ApprovalRecord",
    "ApprovalStatus",
    "BusinessImpact",
    "ContentHash",
    "DecisionAction",
    "DecisionObject",
    "EvidenceLineage",
    "EvidenceObject",
    "EvidenceSource",
    "EvidenceValidationStatus",
    "ExecutionStatus",
    "Exploitability",
    "FindingStatus",
    "FindingType",
    "HashAlgorithm",
    "MetadataBag",
    "OutcomeMetrics",
    "OutcomeObject",
    "OutcomeStatus",
    "PolicyCondition",
    "PolicyEffect",
    "PolicyObject",
    "PolicyRule",
    "PolicyScope",
    "PolicyVerdict",
    "Priority",
    "RecommendedAction",
    "RemediationObject",
    "RemediationPlan",
    "RemediationStep",
    "RollbackPlan",
    "SecurityFindingObject",
    "Severity",
    "SimulationImpact",
    "SimulationObject",
    "SimulationStatus",
    "SourceTool",
    "VerificationCheck",
    "VerificationObject",
    "VerificationStatus",
]
