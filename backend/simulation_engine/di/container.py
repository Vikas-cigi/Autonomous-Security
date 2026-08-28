"""Dependency injection container for Enterprise Simulation Engine."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from simulation_engine.persistence.session import SessionFactory
from simulation_engine.persistence.simulation_audit_repository import (
    PostgresSimulationAuditRepository,
)
from simulation_engine.persistence.simulation_repository import (
    PostgresSimulationRepository,
)
from simulation_engine.services.audit import AuditLogger
from simulation_engine.services.blast_radius import BlastRadiusService
from simulation_engine.services.dependency_analysis import DependencyAnalysisService
from simulation_engine.services.impact_assessment import ImpactAssessmentService
from simulation_engine.services.policy_simulation import PolicySimulationService
from simulation_engine.services.rollback_analysis import RollbackAnalysisService
from simulation_engine.services.simulation_engine_service import SimulationEngineService


@dataclass
class SimulationEngineContainer:
    """
    Composition root for Simulation Engine.

    Example::

        container = SimulationEngineContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            result = svc.engine.simulate(request)
    """

    session_factory: SessionFactory

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> SimulationEngineContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            )
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "SimulationEngineServices":
        audit = AuditLogger(session)
        sim_repo = PostgresSimulationRepository(session, audit_logger=audit)
        audit_repo = PostgresSimulationAuditRepository(session, audit_logger=audit)

        blast = BlastRadiusService()
        deps = DependencyAnalysisService()
        rollback = RollbackAnalysisService()
        policy = PolicySimulationService()
        impact = ImpactAssessmentService(
            blast_radius=blast,
            dependency_analysis=deps,
            rollback_analysis=rollback,
            policy_simulation=policy,
        )
        engine = SimulationEngineService(
            sim_repo,
            audit_repository=audit_repo,
            impact_assessment=impact,
            blast_radius=blast,
            dependency_analysis=deps,
            rollback_analysis=rollback,
            policy_simulation=policy,
            audit_logger=audit,
        )
        return SimulationEngineServices(
            audit=audit,
            engine=engine,
            blast_radius=blast,
            dependency_analysis=deps,
            rollback_analysis=rollback,
            policy_simulation=policy,
            impact_assessment=impact,
            simulation_repository=sim_repo,
            audit_repository=audit_repo,
        )


@dataclass
class SimulationEngineServices:
    """Bundled services sharing one unit-of-work session."""

    audit: AuditLogger
    engine: SimulationEngineService
    blast_radius: BlastRadiusService
    dependency_analysis: DependencyAnalysisService
    rollback_analysis: RollbackAnalysisService
    policy_simulation: PolicySimulationService
    impact_assessment: ImpactAssessmentService
    simulation_repository: PostgresSimulationRepository
    audit_repository: PostgresSimulationAuditRepository
