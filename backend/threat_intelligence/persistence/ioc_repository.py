"""PostgreSQL-compatible IOCRepository."""

from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from models.common import utc_now
from threat_intelligence.domain.enums import AuditAction
from threat_intelligence.domain.ioc import IndicatorOfCompromise
from threat_intelligence.exceptions import IOCNotFoundError
from threat_intelligence.interfaces.ioc_repository import IOCRepository
from threat_intelligence.persistence.mappers import (
    apply_ioc_to_orm,
    ioc_to_orm,
    orm_to_ioc,
)
from threat_intelligence.persistence.orm import IOCRecordORM
from threat_intelligence.query.filters import IOCSearchFilter
from threat_intelligence.query.pagination import Page, PageRequest
from threat_intelligence.services.audit import AuditLogger


class PostgresIOCRepository(IOCRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def save_ioc(
        self,
        ioc: IndicatorOfCompromise,
        *,
        actor: Optional[str] = None,
    ) -> IndicatorOfCompromise:
        existing = self.find_by_value(
            ioc_type=ioc.ioc_type.value,
            normalized_value=ioc.normalized_value,
            tenant_id=ioc.tenant_id,
            include_global=False,
        )
        if existing is None:
            row = self._session.get(IOCRecordORM, ioc.id)
            if row is None:
                version = 1
                ioc.current_version = version
                ioc.touch()
                ioc.last_updated_at = utc_now()
                row = ioc_to_orm(ioc, version=version)
                self._session.add(row)
            else:
                version = int(row.current_version) + 1
                ioc.current_version = version
                ioc.touch()
                ioc.last_updated_at = utc_now()
                apply_ioc_to_orm(row, ioc, version=version)
        else:
            version = existing.current_version + 1
            ioc.id = existing.id
            ioc.current_version = version
            ioc.created_at = existing.created_at
            ioc.first_seen_at = existing.first_seen_at
            ioc.touch()
            ioc.last_updated_at = utc_now()
            row = self._session.get(IOCRecordORM, existing.id)
            assert row is not None
            apply_ioc_to_orm(row, ioc, version=version)

        self._audit.log(
            tenant_id=ioc.tenant_id,
            action=AuditAction.IOC_UPSERTED,
            message=f"IOC upserted: {ioc.ioc_type.value}",
            actor=actor,
            details={"ioc_id": str(ioc.id), "value": ioc.normalized_value},
        )
        self._session.flush()
        return orm_to_ioc(row)

    def get_ioc(
        self,
        ioc_id: UUID,
        *,
        tenant_id: Optional[UUID] = None,
        include_global: bool = True,
    ) -> IndicatorOfCompromise:
        row = self._session.get(IOCRecordORM, ioc_id)
        if row is None:
            raise IOCNotFoundError(ioc_id, tenant_id)
        if tenant_id is not None:
            if row.tenant_id == tenant_id:
                return orm_to_ioc(row)
            if include_global and row.tenant_id is None:
                return orm_to_ioc(row)
            raise IOCNotFoundError(ioc_id, tenant_id)
        return orm_to_ioc(row)

    def find_by_value(
        self,
        *,
        ioc_type: str,
        normalized_value: str,
        tenant_id: Optional[UUID] = None,
        include_global: bool = True,
    ) -> Optional[IndicatorOfCompromise]:
        if tenant_id is not None:
            stmt = select(IOCRecordORM).where(
                IOCRecordORM.ioc_type == ioc_type,
                IOCRecordORM.normalized_value == normalized_value,
                IOCRecordORM.tenant_id == tenant_id,
            )
            row = self._session.scalars(stmt).first()
            if row is not None:
                return orm_to_ioc(row)
            if not include_global:
                return None
        stmt = select(IOCRecordORM).where(
            IOCRecordORM.ioc_type == ioc_type,
            IOCRecordORM.normalized_value == normalized_value,
            IOCRecordORM.tenant_id.is_(None),
        )
        row = self._session.scalars(stmt).first()
        return orm_to_ioc(row) if row else None

    def search_iocs(
        self,
        filters: IOCSearchFilter,
        page: PageRequest,
    ) -> Page[IndicatorOfCompromise]:
        stmt = select(IOCRecordORM)
        if filters.tenant_id is not None:
            if filters.include_global:
                stmt = stmt.where(
                    or_(
                        IOCRecordORM.tenant_id == filters.tenant_id,
                        IOCRecordORM.tenant_id.is_(None),
                    )
                )
            else:
                stmt = stmt.where(IOCRecordORM.tenant_id == filters.tenant_id)
        if filters.ioc_types:
            stmt = stmt.where(
                IOCRecordORM.ioc_type.in_([t.value for t in filters.ioc_types])
            )
        if filters.values:
            norms = [v.strip().lower() for v in filters.values]
            stmt = stmt.where(
                or_(
                    IOCRecordORM.normalized_value.in_(norms),
                    IOCRecordORM.value.in_(filters.values),
                )
            )
        if filters.active_only:
            stmt = stmt.where(IOCRecordORM.is_active.is_(True))
        if filters.min_confidence is not None:
            stmt = stmt.where(
                IOCRecordORM.confidence_score >= filters.min_confidence
            )
        if filters.tags:
            for tag in filters.tags:
                stmt = stmt.where(
                    cast(IOCRecordORM.payload["tags"], String).like(
                        f'%"{tag.lower()}"%'
                    )
                )
        if filters.cve_ids:
            for cve in filters.cve_ids:
                stmt = stmt.where(
                    cast(IOCRecordORM.payload["cve_ids"], String).like(
                        f'%"{cve.upper()}"%'
                    )
                )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(IOCRecordORM.last_seen_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_ioc(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)

    def match_values(
        self,
        *,
        tenant_id: UUID,
        normalized_values: Sequence[str],
        include_global: bool = True,
    ) -> List[IndicatorOfCompromise]:
        if not normalized_values:
            return []
        values = list({v.strip() for v in normalized_values if v.strip()})
        stmt = select(IOCRecordORM).where(
            IOCRecordORM.normalized_value.in_(values),
            IOCRecordORM.is_active.is_(True),
        )
        if include_global:
            stmt = stmt.where(
                or_(
                    IOCRecordORM.tenant_id == tenant_id,
                    IOCRecordORM.tenant_id.is_(None),
                )
            )
        else:
            stmt = stmt.where(IOCRecordORM.tenant_id == tenant_id)
        return [orm_to_ioc(r) for r in self._session.scalars(stmt).all()]
