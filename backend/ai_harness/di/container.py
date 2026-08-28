"""Dependency injection container for Enterprise AI Harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from context.context_manager import ContextManager
from prompt.prompt_builder import PromptBuilder
from providers.provider_factory import ProviderFactory

from ai_harness.persistence.ai_audit_repository import PostgresAIAuditRepository
from ai_harness.persistence.ai_execution_repository import PostgresAIExecutionRepository
from ai_harness.persistence.session import SessionFactory
from ai_harness.services.ai_harness_service import AIHarnessService
from ai_harness.services.confidence import AIConfidenceService
from ai_harness.services.execution import AIExecutionService
from ai_harness.services.provider_routing import AIProviderRoutingService
from ai_harness.services.reflection import AIReflectionService
from ai_harness.services.usage import AIUsageService
from ai_harness.services.validation import AIValidationService


@dataclass
class AIHarnessContainer:
    """
    Composition root for AI Harness.

    Example::

        container = AIHarnessContainer.from_url(
            "sqlite+pysqlite:///:memory:",
            create_tables=True,
        )
        with container.session() as session:
            svc = container.build(session)
            result = await svc.harness.run(request)
    """

    session_factory: SessionFactory
    provider_factory: Optional[ProviderFactory] = None
    context_manager: Optional[ContextManager] = None
    prompt_builder: Optional[PromptBuilder] = None

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
        provider_factory: Optional[ProviderFactory] = None,
        context_manager: Optional[ContextManager] = None,
        prompt_builder: Optional[PromptBuilder] = None,
    ) -> AIHarnessContainer:
        return cls(
            session_factory=SessionFactory(
                database_url,
                echo=echo,
                create_tables=create_tables,
            ),
            provider_factory=provider_factory,
            context_manager=context_manager,
            prompt_builder=prompt_builder,
        )

    def session(self):
        return self.session_factory.session()

    def build(self, session: Session) -> "AIHarnessServices":
        exec_repo = PostgresAIExecutionRepository(session)
        audit_repo = PostgresAIAuditRepository(session)

        routing = AIProviderRoutingService(self.provider_factory)
        validation = AIValidationService()
        reflection = AIReflectionService()
        confidence = AIConfidenceService()
        usage = AIUsageService()

        def audit_cb(**kwargs):
            from ai_harness.domain.enums import AuditAction
            from ai_harness.domain.models import AIAuditRecord

            action = kwargs.get("action")
            action_value = action.value if isinstance(action, AuditAction) else str(action)
            audit_repo.append(
                AIAuditRecord(
                    execution_id=kwargs.get("execution_id"),
                    request_id=kwargs.get("request_id"),
                    tenant_id=kwargs.get("tenant_id"),
                    action=action_value,
                    actor=kwargs.get("actor"),
                    message=kwargs.get("message", ""),
                    details=kwargs.get("details") or {},
                    provider=kwargs.get("provider"),
                )
            )

        execution = AIExecutionService(
            context_manager=self.context_manager,
            prompt_builder=self.prompt_builder,
            routing=routing,
            audit_callback=audit_cb,
        )

        harness = AIHarnessService(
            exec_repo,
            audit_repository=audit_repo,
            execution_service=execution,
            validation_service=validation,
            reflection_service=reflection,
            confidence_service=confidence,
            usage_service=usage,
        )
        return AIHarnessServices(
            harness=harness,
            execution=execution,
            validation=validation,
            reflection=reflection,
            confidence=confidence,
            usage=usage,
            routing=routing,
            execution_repository=exec_repo,
            audit_repository=audit_repo,
        )


@dataclass
class AIHarnessServices:
    """Bundled services sharing one unit-of-work session."""

    harness: AIHarnessService
    execution: AIExecutionService
    validation: AIValidationService
    reflection: AIReflectionService
    confidence: AIConfidenceService
    usage: AIUsageService
    routing: AIProviderRoutingService
    execution_repository: PostgresAIExecutionRepository
    audit_repository: PostgresAIAuditRepository
