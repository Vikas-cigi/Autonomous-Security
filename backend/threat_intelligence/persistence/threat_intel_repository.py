"""PostgreSQL-compatible ThreatIntelRepository."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from models.common import utc_now
from threat_intelligence.domain.enums import AuditAction
from threat_intelligence.domain.history import ThreatIntelHistory, ThreatIntelVersion
from threat_intelligence.domain.models import CVERecord, ThreatIntelligence
from threat_intelligence.exceptions import CVENotFoundError, ThreatIntelNotFoundError
from threat_intelligence.interfaces.threat_intel_repository import ThreatIntelRepository
from threat_intelligence.persistence.mappers import (
    apply_cve_to_orm,
    apply_intel_to_orm,
    cve_to_orm,
    history_from_orm,
    intel_to_orm,
    orm_to_cve,
    orm_to_intel,
    version_from_orm,
)
from threat_intelligence.persistence.orm import (
    CVERecordORM,
    ThreatIntelHistoryORM,
    ThreatIntelVersionORM,
    ThreatIntelligenceORM,
)
from threat_intelligence.query.filters import CVESearchFilter, ThreatIntelSearchFilter
from threat_intelligence.query.pagination import Page, PageRequest
from threat_intelligence.services.audit import AuditLogger


class PostgresThreatIntelRepository(ThreatIntelRepository):
    def __init__(
        self,
        session: Session,
        *,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    def save_intelligence(
        self,
        intel: ThreatIntelligence,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Threat intelligence persisted",
    ) -> ThreatIntelligence:
        row = self._session.get(ThreatIntelligenceORM, intel.id)
        created = row is None
        if created:
            version = 1
            intel.current_version = version
            intel.touch()
            intel.last_updated_at = utc_now()
            row = intel_to_orm(intel, version=version)
            self._session.add(row)
            action = AuditAction.INTEL_CREATED
        else:
            if row.tenant_id != intel.tenant_id:
                raise ThreatIntelNotFoundError(intel.id, intel.tenant_id)
            version = int(row.current_version) + 1
            intel.current_version = version
            intel.touch()
            intel.last_updated_at = utc_now()
            apply_intel_to_orm(row, intel, version=version)
            action = AuditAction.INTEL_UPDATED

        self._session.flush()
        self._session.add(
            ThreatIntelVersionORM(
                id=uuid4(),
                intel_id=intel.id,
                tenant_id=intel.tenant_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=intel.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.add(
            ThreatIntelHistoryORM(
                id=uuid4(),
                intel_id=intel.id,
                tenant_id=intel.tenant_id,
                action=action.value,
                actor=actor,
                message=change_summary,
                details={"version": version},
                created_at=utc_now(),
            )
        )
        self._audit.log(
            tenant_id=intel.tenant_id,
            action=action,
            message=change_summary,
            actor=actor,
            details={"intel_id": str(intel.id), "version": version},
        )
        self._session.flush()
        return orm_to_intel(row)

    def get_intelligence(
        self,
        intel_id: UUID,
        tenant_id: UUID,
    ) -> ThreatIntelligence:
        row = self._session.get(ThreatIntelligenceORM, intel_id)
        if row is None or row.tenant_id != tenant_id:
            raise ThreatIntelNotFoundError(intel_id, tenant_id)
        return orm_to_intel(row)

    def find_by_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> Optional[ThreatIntelligence]:
        stmt = select(ThreatIntelligenceORM).where(
            ThreatIntelligenceORM.tenant_id == tenant_id,
            ThreatIntelligenceORM.finding_id == finding_id,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_intel(row) if row else None

    def search_intelligence(
        self,
        filters: ThreatIntelSearchFilter,
        page: PageRequest,
    ) -> Page[ThreatIntelligence]:
        stmt = select(ThreatIntelligenceORM).where(
            ThreatIntelligenceORM.tenant_id == filters.tenant_id
        )
        if filters.finding_id:
            stmt = stmt.where(ThreatIntelligenceORM.finding_id == filters.finding_id)
        if filters.actively_exploited_only:
            stmt = stmt.where(ThreatIntelligenceORM.actively_exploited.is_(True))
        if filters.in_cisa_kev_only:
            stmt = stmt.where(ThreatIntelligenceORM.in_cisa_kev.is_(True))
        if filters.min_confidence is not None:
            stmt = stmt.where(
                ThreatIntelligenceORM.confidence_score >= filters.min_confidence
            )
        if filters.cve_ids:
            for cve in filters.cve_ids:
                stmt = stmt.where(
                    cast(ThreatIntelligenceORM.payload["cve_ids"], String).like(
                        f'%"{cve.upper()}"%'
                    )
                )
        if filters.text:
            pattern = f"%{filters.text.lower()}%"
            stmt = stmt.where(
                cast(ThreatIntelligenceORM.payload["summary"], String).like(pattern)
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(ThreatIntelligenceORM.last_updated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_intel(r) for r in self._session.scalars(stmt).all()]
        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            message="Threat intelligence search",
            details={"total": total},
        )
        return Page.from_items(items, request=page, total_items=total)

    def list_versions(
        self,
        intel_id: UUID,
        tenant_id: UUID,
    ) -> List[ThreatIntelVersion]:
        self.get_intelligence(intel_id, tenant_id)
        stmt = (
            select(ThreatIntelVersionORM)
            .where(
                ThreatIntelVersionORM.intel_id == intel_id,
                ThreatIntelVersionORM.tenant_id == tenant_id,
            )
            .order_by(ThreatIntelVersionORM.version.asc())
        )
        return [version_from_orm(r) for r in self._session.scalars(stmt).all()]

    def list_history(
        self,
        intel_id: UUID,
        tenant_id: UUID,
    ) -> List[ThreatIntelHistory]:
        self.get_intelligence(intel_id, tenant_id)
        stmt = (
            select(ThreatIntelHistoryORM)
            .where(
                ThreatIntelHistoryORM.intel_id == intel_id,
                ThreatIntelHistoryORM.tenant_id == tenant_id,
            )
            .order_by(ThreatIntelHistoryORM.created_at.asc())
        )
        return [history_from_orm(r) for r in self._session.scalars(stmt).all()]

    def save_cve(
        self,
        record: CVERecord,
        *,
        actor: Optional[str] = None,
    ) -> CVERecord:
        existing = self._find_cve_row(record.cve_id, tenant_id=record.tenant_id)
        if existing is None:
            version = 1
            record.current_version = version
            record.touch()
            record.last_updated_at = utc_now()
            row = cve_to_orm(record, version=version)
            self._session.add(row)
        else:
            version = int(existing.current_version) + 1
            record.id = existing.id
            record.current_version = version
            record.created_at = existing.created_at
            record.touch()
            record.last_updated_at = utc_now()
            apply_cve_to_orm(existing, record, version=version)
            row = existing

        self._audit.log(
            tenant_id=record.tenant_id,
            action=AuditAction.CVE_UPSERTED,
            message=f"CVE upserted: {record.cve_id}",
            actor=actor,
            details={"cve_id": record.cve_id, "version": version},
        )
        self._session.flush()
        return orm_to_cve(row)

    def get_cve(
        self,
        cve_id: str,
        *,
        tenant_id: Optional[UUID] = None,
        include_global: bool = True,
    ) -> CVERecord:
        normalized = cve_id.strip().upper()
        row = self._find_cve_row(
            normalized, tenant_id=tenant_id, include_global=include_global
        )
        if row is None:
            raise CVENotFoundError(normalized, tenant_id)
        return orm_to_cve(row)

    def search_cves(
        self,
        filters: CVESearchFilter,
        page: PageRequest,
    ) -> Page[CVERecord]:
        stmt = select(CVERecordORM)
        clauses = []
        if filters.tenant_id is not None:
            if filters.include_global:
                clauses.append(
                    or_(
                        CVERecordORM.tenant_id == filters.tenant_id,
                        CVERecordORM.tenant_id.is_(None),
                    )
                )
            else:
                clauses.append(CVERecordORM.tenant_id == filters.tenant_id)
        elif not filters.include_global:
            clauses.append(CVERecordORM.tenant_id.is_not(None))

        for clause in clauses:
            stmt = stmt.where(clause)
        if filters.cve_ids:
            stmt = stmt.where(
                CVERecordORM.cve_id.in_([c.upper() for c in filters.cve_ids])
            )
        if filters.in_cisa_kev_only:
            stmt = stmt.where(CVERecordORM.in_cisa_kev.is_(True))
        if filters.actively_exploited_only:
            stmt = stmt.where(CVERecordORM.actively_exploited.is_(True))
        if filters.min_epss is not None:
            stmt = stmt.where(CVERecordORM.epss_score >= filters.min_epss)
        if filters.cwe_ids:
            for cwe in filters.cwe_ids:
                stmt = stmt.where(
                    cast(CVERecordORM.payload["cwe_ids"], String).like(
                        f'%"{cwe.upper()}"%'
                    )
                )
        if filters.text:
            pattern = f"%{filters.text.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(CVERecordORM.cve_id).like(pattern),
                    cast(CVERecordORM.payload["title"], String).like(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            stmt.order_by(CVERecordORM.last_updated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        items = [orm_to_cve(r) for r in self._session.scalars(stmt).all()]
        return Page.from_items(items, request=page, total_items=total)

    def _find_cve_row(
        self,
        cve_id: str,
        *,
        tenant_id: Optional[UUID],
        include_global: bool = True,
    ) -> Optional[CVERecordORM]:
        if tenant_id is not None:
            stmt = select(CVERecordORM).where(
                CVERecordORM.cve_id == cve_id,
                CVERecordORM.tenant_id == tenant_id,
            )
            row = self._session.scalars(stmt).first()
            if row is not None:
                return row
            if not include_global:
                return None
        stmt = select(CVERecordORM).where(
            CVERecordORM.cve_id == cve_id,
            CVERecordORM.tenant_id.is_(None),
        )
        return self._session.scalars(stmt).first()
