"""
Enterprise AI Harness.

Centralized orchestration for every AI interaction in Xolaris. Wraps
Context Manager, Prompt Builder, and Provider Factory with validation,
resilience, observability, and governance.

No cybersecurity business logic. No REST APIs. Does not modify existing modules.
"""

from ai_harness.di.container import AIHarnessContainer, AIHarnessServices
from ai_harness.domain.enums import AIExecutionStatus, ConfidenceBand, ReflectionMode
from ai_harness.domain.models import (
    AIAuditRecord,
    AIConfidence,
    AIExecution,
    AIExecutionResult,
    AIProviderResult,
    AIReflection,
    AIRequest,
    AIResponse,
    AIUsageMetrics,
    AIValidationResult,
)
from ai_harness.interfaces.ai_audit_repository import AIAuditRepository
from ai_harness.interfaces.ai_execution_repository import AIExecutionRepository
from ai_harness.services.ai_harness_service import AIHarnessService

__all__ = [
    "AIAuditRecord",
    "AIAuditRepository",
    "AIConfidence",
    "AIExecution",
    "AIExecutionRepository",
    "AIExecutionResult",
    "AIExecutionStatus",
    "AIHarnessContainer",
    "AIHarnessService",
    "AIHarnessServices",
    "AIProviderResult",
    "AIReflection",
    "AIRequest",
    "AIResponse",
    "AIUsageMetrics",
    "AIValidationResult",
    "ConfidenceBand",
    "ReflectionMode",
]

__version__ = "1.0.0"
