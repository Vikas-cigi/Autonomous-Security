"""
Enterprise Simulation Engine.

Performs a dry-run simulation of a RemediationPlan before any execution.
Predicts impact without infrastructure changes or external API calls.

Pipeline position: after Remediation Planner, before Approval Engine.
"""

from simulation_engine.di.container import (
    SimulationEngineContainer,
    SimulationEngineServices,
)
from simulation_engine.domain.enums import BlastRadiusTier, SimulationOutcome
from simulation_engine.domain.history import SimulationAuditRecord, SimulationVersionRecord
from simulation_engine.domain.inputs import SimulationRequest
from simulation_engine.domain.models import (
    BlastRadius,
    DependencyImpact,
    DowntimeEstimate,
    ImpactAssessment,
    PolicyImpact,
    RiskReductionEstimate,
    RollbackAssessment,
    SimulationResult,
    SimulationStep,
)
from simulation_engine.interfaces.simulation_audit_repository import (
    SimulationAuditRepository,
)
from simulation_engine.interfaces.simulation_repository import SimulationRepository
from simulation_engine.services.simulation_engine_service import SimulationEngineService

__all__ = [
    "BlastRadius",
    "BlastRadiusTier",
    "DependencyImpact",
    "DowntimeEstimate",
    "ImpactAssessment",
    "PolicyImpact",
    "RiskReductionEstimate",
    "RollbackAssessment",
    "SimulationAuditRecord",
    "SimulationAuditRepository",
    "SimulationEngineContainer",
    "SimulationEngineService",
    "SimulationEngineServices",
    "SimulationOutcome",
    "SimulationRepository",
    "SimulationRequest",
    "SimulationResult",
    "SimulationStep",
    "SimulationVersionRecord",
]

__version__ = "1.0.0"
