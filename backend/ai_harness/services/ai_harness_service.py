"""AIHarnessService — centralized facade for all Xolaris AI interactions."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from models.common import utc_now

from ai_harness.domain.enums import AIExecutionStatus, AuditAction
from ai_harness.domain.models import (
    AIExecution,
    AIExecutionResult,
    AIRequest,
    AIResponse,
)
from ai_harness.domain.weights import ALGORITHM_VERSION
from ai_harness.exceptions import (
    AIProviderExhaustedError,
    AIValidationError,
    InvalidAIRequestError,
)
from ai_harness.interfaces.ai_audit_repository import AIAuditRepository
from ai_harness.interfaces.ai_execution_repository import AIExecutionRepository
from ai_harness.query.filters import AIExecutionSearchFilter
from ai_harness.query.pagination import Page, PageRequest
from ai_harness.services.confidence import AIConfidenceService
from ai_harness.services.execution import AIExecutionService
from ai_harness.services.reflection import AIReflectionService
from ai_harness.services.usage import AIUsageService
from ai_harness.services.validation import AIValidationService

logger = logging.getLogger(__name__)


class AIHarnessService:
    """
    Central orchestration layer for AI interactions.

    Pipeline position: after Decision Service (and usable by any caller),
    before Remediation Planner consumes AI outputs.

    Reuses Context Manager, Prompt Builder, Provider Factory.
    Contains no cybersecurity business logic.
    """

    def __init__(
        self,
        execution_repository: AIExecutionRepository,
        *,
        audit_repository: Optional[AIAuditRepository] = None,
        execution_service: Optional[AIExecutionService] = None,
        validation_service: Optional[AIValidationService] = None,
        reflection_service: Optional[AIReflectionService] = None,
        confidence_service: Optional[AIConfidenceService] = None,
        usage_service: Optional[AIUsageService] = None,
    ) -> None:
        self._exec_repo = execution_repository
        self._audit_repo = audit_repository
        self._validation = validation_service or AIValidationService()
        self._reflection = reflection_service or AIReflectionService()
        self._confidence = confidence_service or AIConfidenceService()
        self._usage = usage_service or AIUsageService()

        def _audit_cb(**kwargs):
            self._record_audit(**kwargs)

        self._execution = execution_service or AIExecutionService(
            audit_callback=_audit_cb
        )
        # If a custom execution_service was injected without callback, still OK.

    async def run(
        self,
        request: AIRequest,
        *,
        persist: bool = True,
        raise_on_validation_error: bool = False,
    ) -> AIExecutionResult:
        """Execute a full harness cycle and optionally persist the execution."""

        self._validate_request(request)
        execution = AIExecution(
            tenant_id=request.tenant_id,
            request_id=request.id,
            correlation_id=request.correlation_id,
            status=AIExecutionStatus.RUNNING,
            primary_provider=request.provider_name,
            request_snapshot=request.model_dump(mode="json"),
            algorithm_version=ALGORITHM_VERSION,
            started_at=utc_now(),
        )
        self._record_audit(
            action=AuditAction.EXECUTION_STARTED,
            message="AI harness execution started",
            tenant_id=request.tenant_id,
            request_id=request.id,
            execution_id=execution.id,
            actor=request.actor,
        )

        try:
            text, attempts, selected = await self._execution.execute_with_resilience(
                request
            )
            execution.provider_results = attempts
            execution.selected_provider = selected
            execution.attempt_count = len(attempts)
            successful = next(a for a in reversed(attempts) if a.success)

            validation = self._validation.validate(request, text)
            self._record_audit(
                action=AuditAction.VALIDATION_COMPLETED,
                message=f"Validation valid={validation.valid}",
                tenant_id=request.tenant_id,
                request_id=request.id,
                execution_id=execution.id,
                details={
                    "valid": validation.valid,
                    "error_count": validation.error_count,
                },
            )

            if raise_on_validation_error and not validation.valid:
                execution.status = AIExecutionStatus.VALIDATION_FAILED
                execution.error_message = "Structured output validation failed"
                execution.completed_at = utc_now()
                if persist:
                    execution = self._exec_repo.save(execution)
                raise AIValidationError(
                    "Structured output validation failed",
                    details={"issues": [i.model_dump() for i in validation.issues]},
                )

            reflection = await self._reflection.maybe_reflect(
                request=request,
                provider=self._execution._routing.get_provider(selected),
                primary_text=text,
                validation=validation,
            )
            final_text = text
            if reflection.performed and reflection.reflection_text:
                final_text = reflection.reflection_text
                # Re-validate reflected text when structured output expected.
                if request.expect_json or request.json_schema or request.required_json_keys:
                    validation = self._validation.validate(request, final_text)
                self._record_audit(
                    action=AuditAction.REFLECTION_COMPLETED,
                    message=f"Reflection improved={reflection.improved}",
                    tenant_id=request.tenant_id,
                    request_id=request.id,
                    execution_id=execution.id,
                    provider=selected,
                )

            confidence = self._confidence.evaluate(
                text=final_text,
                validation=validation,
                provider_result=successful,
                reflected=reflection.performed,
            )
            usage = self._usage.from_provider_result(successful)
            # Include failed attempt latency in aggregate usage view
            if len(attempts) > 1:
                usage = self._usage.merge(
                    *[self._usage.from_provider_result(a) for a in attempts]
                )

            status = (
                AIExecutionStatus.SUCCEEDED
                if validation.valid or not (
                    request.expect_json or request.json_schema or request.required_json_keys
                )
                else AIExecutionStatus.VALIDATION_FAILED
            )
            execution.status = status
            execution.completed_at = utc_now()
            if status == AIExecutionStatus.VALIDATION_FAILED:
                execution.error_message = "Structured output validation failed"

            response = AIResponse(
                request_id=request.id,
                text=final_text,
                provider=selected,
                model=successful.model,
                finish_reason=successful.finish_reason,
                structured_payload=validation.parsed_payload,
                confidence=confidence,
                usage=usage,
                validation=validation,
                reflection=reflection,
                metadata={"harness_version": ALGORITHM_VERSION},
            )

            if persist:
                execution = self._exec_repo.save(execution)

            self._record_audit(
                action=(
                    AuditAction.EXECUTION_SUCCEEDED
                    if status == AIExecutionStatus.SUCCEEDED
                    else AuditAction.EXECUTION_FAILED
                ),
                message=f"Execution finished status={status.value}",
                tenant_id=request.tenant_id,
                request_id=request.id,
                execution_id=execution.id,
                provider=selected,
                actor=request.actor,
            )

            return AIExecutionResult(
                execution=execution,
                request=request,
                response=response,
                success=status == AIExecutionStatus.SUCCEEDED,
                status=status,
                error_message=execution.error_message,
            )

        except AIValidationError:
            raise
        except AIProviderExhaustedError as exc:
            execution.status = AIExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = utc_now()
            if isinstance(exc.details, dict) and "attempts" in exc.details:
                # attempts already serialized; leave provider_results as-is if set
                pass
            if persist:
                execution = self._exec_repo.save(execution)
            self._record_audit(
                action=AuditAction.EXECUTION_FAILED,
                message=str(exc),
                tenant_id=request.tenant_id,
                request_id=request.id,
                execution_id=execution.id,
                actor=request.actor,
            )
            return AIExecutionResult(
                execution=execution,
                request=request,
                response=None,
                success=False,
                status=execution.status,
                error_message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("AI harness unexpected failure")
            execution.status = AIExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = utc_now()
            if persist:
                execution = self._exec_repo.save(execution)
            self._record_audit(
                action=AuditAction.EXECUTION_FAILED,
                message=str(exc),
                tenant_id=request.tenant_id,
                request_id=request.id,
                execution_id=execution.id,
                actor=request.actor,
            )
            return AIExecutionResult(
                execution=execution,
                request=request,
                response=None,
                success=False,
                status=execution.status,
                error_message=str(exc),
            )

    def get_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> AIExecution:
        return self._exec_repo.get(execution_id, tenant_id)

    def search(
        self,
        filters: AIExecutionSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[AIExecution]:
        return self._exec_repo.search(filters, page or PageRequest())

    @staticmethod
    def _validate_request(request: AIRequest) -> None:
        if not request.message.strip():
            raise InvalidAIRequestError("message must not be blank")
        if request.expect_json and request.json_schema is None and not request.required_json_keys:
            # Soft rule: allow expect_json alone (must still parse as object)
            pass

    def _record_audit(
        self,
        *,
        action: AuditAction,
        message: str,
        tenant_id=None,
        request_id=None,
        execution_id=None,
        actor=None,
        provider=None,
        details=None,
    ) -> None:
        if self._audit_repo is None:
            return
        from ai_harness.domain.models import AIAuditRecord

        self._audit_repo.append(
            AIAuditRecord(
                execution_id=execution_id,
                request_id=request_id,
                tenant_id=tenant_id,
                action=action.value,
                actor=actor,
                message=message,
                details=details or {},
                provider=provider,
            )
        )
