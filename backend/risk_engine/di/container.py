"""Dependency injection container for Enterprise Risk Engine."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from risk_engine.persistence.risk_history_repository import PostgresRiskHistoryRepository
from risk_engine.persistence.risk_repository import PostgresRiskRepository
from risk_engine.persistence.session import SessionFactory
from risk_engine.services.audit import AuditLogger
from risk_engine.services.business_risk import BusinessRiskService
from risk_engine.services.compliance_risk import ComplianceRiskService
from risk_engine.services.exposure_risk import ExposureRiskService
from risk_engine.services.risk_aggregation import RiskAggregationService
from risk_engine.services.risk_engine_service import RiskEngineService
from risk_engine.services.technical_risk import TechnicalRiskService


@dataclass
class RiskEngineContainer:
    """
    Composition root for Risk Engine repositories and services.

    Example::

        container = RiskEngineContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            assessment = svc.risk_engine.score(scoring_input)
    """

    session_factory: SessionFactory

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
    ) -> RiskEngineContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            )
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "RiskEngineServices":
        audit = AuditLogger(session)
        risk_repo = PostgresRiskRepository(session, audit_logger=audit)
        history_repo = PostgresRiskHistoryRepository(session, audit_logger=audit)

        technical = TechnicalRiskService()
        business = BusinessRiskService()
        compliance = ComplianceRiskService()
        exposure = ExposureRiskService()
        aggregation = RiskAggregationService()

        risk_engine = RiskEngineService(
            risk_repo,
            history_repository=history_repo,
            technical_service=technical,
            business_service=business,
            compliance_service=compliance,
            exposure_service=exposure,
            aggregation_service=aggregation,
            audit_logger=audit,
        )
        return RiskEngineServices(
            audit=audit,
            risk_engine=risk_engine,
            technical_risk=technical,
            business_risk=business,
            compliance_risk=compliance,
            exposure_risk=exposure,
            aggregation=aggregation,
            risk_repository=risk_repo,
            history_repository=history_repo,
        )


@dataclass
class RiskEngineServices:
    """Bundled services sharing one unit-of-work session."""

    audit: AuditLogger
    risk_engine: RiskEngineService
    technical_risk: TechnicalRiskService
    business_risk: BusinessRiskService
    compliance_risk: ComplianceRiskService
    exposure_risk: ExposureRiskService
    aggregation: RiskAggregationService
    risk_repository: PostgresRiskRepository
    history_repository: PostgresRiskHistoryRepository
