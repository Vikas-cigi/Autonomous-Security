"""Dependency injection container for Enterprise Decision Service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from policy_engine.engine import PolicyEngine

from decision_service.adapters.ai_stack_gateway import AIStackGateway
from decision_service.interfaces.ai_gateway import AIDecisionGateway
from decision_service.persistence.decision_audit_repository import (
    PostgresDecisionAuditRepository,
)
from decision_service.persistence.decision_repository import PostgresDecisionRepository
from decision_service.persistence.session import SessionFactory
from decision_service.services.audit_service import DecisionAuditService
from decision_service.services.context_assembler import DecisionContextAssembler
from decision_service.services.decision_service import DecisionService
from decision_service.services.deterministic_advisor import DeterministicDecisionAdvisor
from decision_service.services.explanation_service import DecisionExplanationService
from decision_service.services.recommendation_parser import DecisionRecommendationParser
from decision_service.services.validation_service import DecisionValidationService


@dataclass
class DecisionServiceContainer:
    """
    Composition root for Decision Service repositories and collaborators.

    Example::

        container = DecisionServiceContainer.from_url(
            "postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            response = await svc.decision.decide(request)
    """

    session_factory: SessionFactory
    policy_engine: Optional[PolicyEngine] = None
    ai_gateway: Optional[AIDecisionGateway] = None
    enable_ai_stack: bool = True

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
        policy_engine: Optional[PolicyEngine] = None,
        ai_gateway: Optional[AIDecisionGateway] = None,
        enable_ai_stack: bool = True,
    ) -> DecisionServiceContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            ),
            policy_engine=policy_engine,
            ai_gateway=ai_gateway,
            enable_ai_stack=enable_ai_stack,
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "DecisionServiceBundle":
        decision_repo = PostgresDecisionRepository(session)
        audit_repo = PostgresDecisionAuditRepository(session)
        audit = DecisionAuditService(audit_repo)

        validation = DecisionValidationService(policy_engine=self.policy_engine)
        assembler = DecisionContextAssembler()
        explanation = DecisionExplanationService()
        deterministic = DeterministicDecisionAdvisor()
        parser = DecisionRecommendationParser()

        gateway = self.ai_gateway
        if gateway is None and self.enable_ai_stack:
            gateway = AIStackGateway()

        decision = DecisionService(
            decision_repo,
            audit_service=audit,
            context_assembler=assembler,
            validation_service=validation,
            explanation_service=explanation,
            deterministic_advisor=deterministic,
            recommendation_parser=parser,
            ai_gateway=gateway,
        )
        return DecisionServiceBundle(
            decision=decision,
            audit=audit,
            context_assembler=assembler,
            validation=validation,
            explanation=explanation,
            deterministic_advisor=deterministic,
            recommendation_parser=parser,
            decision_repository=decision_repo,
            audit_repository=audit_repo,
            ai_gateway=gateway,
        )


@dataclass
class DecisionServiceBundle:
    """Bundled services sharing one unit-of-work session."""

    decision: DecisionService
    audit: DecisionAuditService
    context_assembler: DecisionContextAssembler
    validation: DecisionValidationService
    explanation: DecisionExplanationService
    deterministic_advisor: DeterministicDecisionAdvisor
    recommendation_parser: DecisionRecommendationParser
    decision_repository: PostgresDecisionRepository
    audit_repository: PostgresDecisionAuditRepository
    ai_gateway: Optional[AIDecisionGateway]
