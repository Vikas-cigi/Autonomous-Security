"""Map between AI Harness domain models and ORM rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ai_harness.domain.models import AIAuditRecord, AIExecution
from ai_harness.persistence.orm import AIAuditORM, AIExecutionORM


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def execution_to_orm(execution: AIExecution) -> AIExecutionORM:
    return AIExecutionORM(
        id=execution.id,
        tenant_id=execution.tenant_id,
        request_id=execution.request_id,
        correlation_id=execution.correlation_id,
        status=execution.status.value,
        primary_provider=execution.primary_provider,
        selected_provider=execution.selected_provider,
        attempt_count=execution.attempt_count,
        algorithm_version=execution.algorithm_version,
        payload=execution.model_dump(mode="json"),
        error_message=execution.error_message,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
    )


def apply_execution_to_orm(row: AIExecutionORM, execution: AIExecution) -> None:
    row.correlation_id = execution.correlation_id
    row.status = execution.status.value
    row.primary_provider = execution.primary_provider
    row.selected_provider = execution.selected_provider
    row.attempt_count = execution.attempt_count
    row.algorithm_version = execution.algorithm_version
    row.payload = execution.model_dump(mode="json")
    row.error_message = execution.error_message
    row.started_at = execution.started_at
    row.completed_at = execution.completed_at
    row.updated_at = execution.updated_at


def orm_to_execution(row: AIExecutionORM) -> AIExecution:
    return AIExecution.model_validate(row.payload)


def audit_to_orm(record: AIAuditRecord) -> AIAuditORM:
    return AIAuditORM(
        id=record.id,
        execution_id=record.execution_id,
        request_id=record.request_id,
        tenant_id=record.tenant_id,
        action=record.action,
        actor=record.actor,
        message=record.message,
        provider=record.provider,
        details=record.details,
        created_at=record.created_at,
    )


def audit_from_orm(row: AIAuditORM) -> AIAuditRecord:
    return AIAuditRecord(
        id=row.id,
        execution_id=row.execution_id,
        request_id=row.request_id,
        tenant_id=row.tenant_id,
        action=row.action,
        actor=row.actor,
        message=row.message,
        details=row.details or {},
        provider=row.provider,
        created_at=_as_utc(row.created_at) or row.created_at,
    )
