"""Dependency injection container for Enterprise Remediation Planner."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from remediation_planner.persistence.remediation_history_repository import (
    PostgresRemediationHistoryRepository,
)
from remediation_planner.persistence.remediation_plan_repository import (
    PostgresRemediationPlanRepository,
)
from remediation_planner.persistence.session import SessionFactory
from remediation_planner.services.audit import AuditLogger
from remediation_planner.services.cost_estimation import CostEstimationService
from remediation_planner.services.dependency_resolution import DependencyResolutionService
from remediation_planner.services.impact_analysis import ImpactAnalysisService
from remediation_planner.services.plan_generation import PlanGenerationService
from remediation_planner.services.remediation_planner_service import (
    RemediationPlannerService,
)
from remediation_planner.services.rollback_planning import RollbackPlanningService


@dataclass
class RemediationPlannerContainer:
    """
    Composition root for Remediation Planner.

    Example::

        container = RemediationPlannerContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            plan = svc.planner.plan(request)
    """

    session_factory: SessionFactory

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> RemediationPlannerContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            )
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "RemediationPlannerServices":
        audit = AuditLogger(session)
        plan_repo = PostgresRemediationPlanRepository(session, audit_logger=audit)
        history_repo = PostgresRemediationHistoryRepository(
            session, audit_logger=audit
        )

        generation = PlanGenerationService()
        dependencies = DependencyResolutionService()
        rollback = RollbackPlanningService()
        impact = ImpactAnalysisService()
        cost = CostEstimationService()

        planner = RemediationPlannerService(
            plan_repo,
            history_repository=history_repo,
            plan_generation=generation,
            dependency_resolution=dependencies,
            rollback_planning=rollback,
            impact_analysis=impact,
            cost_estimation=cost,
            audit_logger=audit,
        )
        return RemediationPlannerServices(
            audit=audit,
            planner=planner,
            plan_generation=generation,
            dependency_resolution=dependencies,
            rollback_planning=rollback,
            impact_analysis=impact,
            cost_estimation=cost,
            plan_repository=plan_repo,
            history_repository=history_repo,
        )


@dataclass
class RemediationPlannerServices:
    """Bundled services sharing one unit-of-work session."""

    audit: AuditLogger
    planner: RemediationPlannerService
    plan_generation: PlanGenerationService
    dependency_resolution: DependencyResolutionService
    rollback_planning: RollbackPlanningService
    impact_analysis: ImpactAnalysisService
    cost_estimation: CostEstimationService
    plan_repository: PostgresRemediationPlanRepository
    history_repository: PostgresRemediationHistoryRepository
