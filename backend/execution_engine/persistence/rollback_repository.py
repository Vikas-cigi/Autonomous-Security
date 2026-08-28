"""PostgreSQL-compatible RollbackRepository (embedded in execution payload)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.common import utc_now
from execution_engine.domain.models import RollbackExecution
from execution_engine.exceptions import ExecutionNotFoundError
from execution_engine.interfaces.rollback_repository import RollbackRepository
from execution_engine.persistence.mappers import apply_result_to_orm, orm_to_result
from execution_engine.persistence.orm import ExecutionResultORM


class PostgresRollbackRepository(RollbackRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self, execution_id: UUID, tenant_id: UUID, rollback: RollbackExecution
    ) -> RollbackExecution:
        row = self._session.get(ExecutionResultORM, execution_id)
        if row is None or row.tenant_id != tenant_id:
            raise ExecutionNotFoundError(execution_id, tenant_id)
        result = orm_to_result(row)
        result.rollback_execution = rollback
        result.touch()
        result.last_evaluated_at = utc_now()
        apply_result_to_orm(row, result, version=int(row.current_version))
        self._session.flush()
        return orm_to_result(row).rollback_execution or rollback

    def get(
        self, execution_id: UUID, tenant_id: UUID
    ) -> Optional[RollbackExecution]:
        row = self._session.get(ExecutionResultORM, execution_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return orm_to_result(row).rollback_execution
