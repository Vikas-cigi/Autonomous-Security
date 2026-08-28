"""
PostgreSQL-compatible EvidenceRepository implementation (SQLAlchemy 2.x).
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from models.common import utc_now
from models.enums import FindingStatus
from models.evidence import EvidenceObject
from models.security_finding import SecurityFindingObject
from evidence_repository.domain.enums import (
    AuditAction,
    LifecycleState,
    statuses_for_lifecycle,
    to_finding_status,
    to_lifecycle,
)
from evidence_repository.domain.history import FindingHistory
from evidence_repository.domain.versioning import EvidenceVersion, FindingVersion
from evidence_repository.exceptions import (
    EvidenceNotFoundError,
    FindingNotFoundError,
    TenantIsolationError,
)
from evidence_repository.fingerprint import finding_fingerprint
from evidence_repository.interfaces.repository import EvidenceRepository
from evidence_repository.persistence.mappers import (
    apply_evidence_to_orm,
    apply_finding_to_orm,
    evidence_to_orm,
    evidence_version_from_orm,
    finding_to_orm,
    finding_version_from_orm,
    history_from_orm,
    orm_to_evidence,
    orm_to_finding,
)
from evidence_repository.persistence.orm import (
    AuditLogORM,
    EvidenceORM,
    EvidenceVersionORM,
    FindingHistoryORM,
    FindingORM,
    FindingVersionORM,
)
from evidence_repository.query.filters import FindingSearchFilter
from evidence_repository.query.pagination import Page, PageRequest
from evidence_repository.services.audit import AuditLogger

logger = logging.getLogger(__name__)


class PostgresEvidenceRepository(EvidenceRepository):
    """
    SQLAlchemy-backed repository.

    Works with PostgreSQL (production) and SQLite (tests) via portable types.
    """

    def __init__(self, session: Session, *, audit_logger: Optional[AuditLogger] = None) -> None:
        self._session = session
        self._audit = audit_logger or AuditLogger(session)

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def save_finding(
        self,
        finding: SecurityFindingObject,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Initial persist",
    ) -> SecurityFindingObject:
        row = self._session.get(FindingORM, finding.id)
        if row is not None and row.tenant_id != finding.tenant_id:
            raise TenantIsolationError(
                "Finding id exists under a different tenant",
                details={"finding_id": str(finding.id)},
            )

        if row is None:
            version = 1
            row = finding_to_orm(finding, current_version=version)
            self._session.add(row)
            action = AuditAction.FINDING_CREATED
            message = "Finding created"
        else:
            version = int(row.current_version) + 1
            apply_finding_to_orm(row, finding, current_version=version)
            finding = finding.model_copy(update={"updated_at": utc_now()})
            row.payload = finding.model_dump(mode="json")
            row.updated_at = finding.updated_at
            action = AuditAction.FINDING_UPDATED
            message = "Finding updated"

        self._session.add(
            FindingVersionORM(
                id=uuid4(),
                finding_id=finding.id,
                tenant_id=finding.tenant_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=finding.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._add_history(
            FindingHistory(
                finding_id=finding.id,
                tenant_id=finding.tenant_id,
                action=action,
                to_status=finding.status,
                to_lifecycle=to_lifecycle(finding.status),
                actor=actor,
                message=message,
                details={"version": version, "fingerprint": finding_fingerprint(finding)},
            )
        )

        # Upsert embedded evidence
        for evidence in finding.evidence:
            self._upsert_evidence_row(
                finding_id=finding.id,
                tenant_id=finding.tenant_id,
                evidence=evidence,
                actor=actor,
                change_summary="Synced with finding save",
            )

        self._session.flush()
        self._audit.log(
            tenant_id=finding.tenant_id,
            action=action,
            actor=actor,
            message=message,
            details={"finding_id": str(finding.id), "version": version},
        )
        logger.info(
            "Saved finding id=%s tenant=%s version=%s",
            finding.id,
            finding.tenant_id,
            version,
        )
        return orm_to_finding(row)

    def get_finding(self, finding_id: UUID, tenant_id: UUID) -> SecurityFindingObject:
        row = self._require_finding(finding_id, tenant_id)
        return orm_to_finding(row)

    def update_status(
        self,
        finding_id: UUID,
        tenant_id: UUID,
        status: FindingStatus,
        *,
        actor: Optional[str] = None,
        message: str = "Status updated",
    ) -> SecurityFindingObject:
        row = self._require_finding(finding_id, tenant_id)
        finding = orm_to_finding(row)
        if finding.status is status:
            return finding

        previous = finding.status
        updated = finding.model_copy(
            update={"status": status, "updated_at": utc_now()}
        )
        self._add_history(
            FindingHistory.status_change(
                finding_id=finding_id,
                tenant_id=tenant_id,
                from_status=previous,
                to_status=status,
                actor=actor,
                message=message,
            )
        )
        return self.save_finding(
            updated,
            actor=actor,
            change_summary=f"Status {previous.value} → {status.value}: {message}",
        )

    def update_lifecycle(
        self,
        finding_id: UUID,
        tenant_id: UUID,
        lifecycle: LifecycleState,
        *,
        actor: Optional[str] = None,
        message: str = "Lifecycle updated",
    ) -> SecurityFindingObject:
        return self.update_status(
            finding_id,
            tenant_id,
            to_finding_status(lifecycle),
            actor=actor,
            message=message,
        )

    def list_finding_versions(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[FindingVersion]:
        self._require_finding(finding_id, tenant_id)
        stmt = (
            select(FindingVersionORM)
            .where(
                FindingVersionORM.finding_id == finding_id,
                FindingVersionORM.tenant_id == tenant_id,
            )
            .order_by(FindingVersionORM.version.asc())
        )
        rows = self._session.scalars(stmt).all()
        return [finding_version_from_orm(row) for row in rows]

    def list_finding_history(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[FindingHistory]:
        self._require_finding(finding_id, tenant_id)
        stmt = (
            select(FindingHistoryORM)
            .where(
                FindingHistoryORM.finding_id == finding_id,
                FindingHistoryORM.tenant_id == tenant_id,
            )
            .order_by(FindingHistoryORM.created_at.asc())
        )
        rows = self._session.scalars(stmt).all()
        return [history_from_orm(row) for row in rows]

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def save_evidence(
        self,
        finding_id: UUID,
        tenant_id: UUID,
        evidence: EvidenceObject,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Evidence attached",
    ) -> EvidenceObject:
        self._require_finding(finding_id, tenant_id)
        row = self._upsert_evidence_row(
            finding_id=finding_id,
            tenant_id=tenant_id,
            evidence=evidence,
            actor=actor,
            change_summary=change_summary,
        )
        finding_row = self._require_finding(finding_id, tenant_id)
        finding = orm_to_finding(finding_row)
        evidence_map = {item.id: item for item in finding.evidence}
        evidence_map[evidence.id] = evidence
        synced = finding.model_copy(
            update={
                "evidence": list(evidence_map.values()),
                "updated_at": utc_now(),
            }
        )
        version = int(finding_row.current_version) + 1
        apply_finding_to_orm(finding_row, synced, current_version=version)
        self._session.add(
            FindingVersionORM(
                id=uuid4(),
                finding_id=finding_id,
                tenant_id=tenant_id,
                version=version,
                change_summary=f"Evidence sync: {change_summary}",
                created_by=actor,
                payload=synced.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._session.flush()
        self._audit.log(
            tenant_id=tenant_id,
            action=AuditAction.EVIDENCE_ATTACHED,
            actor=actor,
            message=change_summary,
            details={
                "finding_id": str(finding_id),
                "evidence_id": str(evidence.id),
                "version": int(row.current_version),
            },
        )
        return orm_to_evidence(row)

    def get_evidence(self, evidence_id: UUID, tenant_id: UUID) -> EvidenceObject:
        row = self._session.get(EvidenceORM, evidence_id)
        if row is None or row.tenant_id != tenant_id:
            raise EvidenceNotFoundError(evidence_id, tenant_id)
        return orm_to_evidence(row)

    def list_evidence_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[EvidenceObject]:
        self._require_finding(finding_id, tenant_id)
        stmt = select(EvidenceORM).where(
            EvidenceORM.finding_id == finding_id,
            EvidenceORM.tenant_id == tenant_id,
        )
        rows = self._session.scalars(stmt).all()
        return [orm_to_evidence(row) for row in rows]

    def list_evidence_versions(
        self,
        evidence_id: UUID,
        tenant_id: UUID,
    ) -> List[EvidenceVersion]:
        self.get_evidence(evidence_id, tenant_id)
        stmt = (
            select(EvidenceVersionORM)
            .where(
                EvidenceVersionORM.evidence_id == evidence_id,
                EvidenceVersionORM.tenant_id == tenant_id,
            )
            .order_by(EvidenceVersionORM.version.asc())
        )
        rows = self._session.scalars(stmt).all()
        return [evidence_version_from_orm(row) for row in rows]

    # ------------------------------------------------------------------
    # Search / correlation
    # ------------------------------------------------------------------

    def search_findings(
        self,
        filters: FindingSearchFilter,
        page: PageRequest,
    ) -> Page[SecurityFindingObject]:
        stmt = self._build_search_query(filters)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.scalar(count_stmt) or 0)

        stmt = (
            stmt.order_by(FindingORM.updated_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        rows = self._session.scalars(stmt).all()
        items = [orm_to_finding(row) for row in rows]

        self._audit.log(
            tenant_id=filters.tenant_id,
            action=AuditAction.SEARCHED,
            actor=None,
            message="Finding search executed",
            details={
                "total": total,
                "page": page.page,
                "page_size": page.page_size,
                "filters": filters.model_dump(mode="json", exclude_none=True),
            },
        )
        return Page.from_items(items, request=page, total_items=total)

    def find_by_fingerprint(
        self,
        tenant_id: UUID,
        fingerprint: str,
    ) -> Optional[SecurityFindingObject]:
        stmt = select(FindingORM).where(
            FindingORM.tenant_id == tenant_id,
            FindingORM.fingerprint == fingerprint,
        )
        row = self._session.scalars(stmt).first()
        return orm_to_finding(row) if row else None

    def set_correlation_group(
        self,
        tenant_id: UUID,
        finding_ids: Sequence[UUID],
        correlation_group_id: UUID,
        *,
        actor: Optional[str] = None,
    ) -> int:
        updated = 0
        for finding_id in finding_ids:
            row = self._require_finding(finding_id, tenant_id)
            row.correlation_group_id = correlation_group_id
            finding = orm_to_finding(row)
            finding.metadata.labels["correlation_group_id"] = str(correlation_group_id)
            row.payload = finding.model_dump(mode="json")
            self._add_history(
                FindingHistory(
                    finding_id=finding_id,
                    tenant_id=tenant_id,
                    action=AuditAction.CORRELATED,
                    actor=actor,
                    message="Assigned to correlation group",
                    details={"correlation_group_id": str(correlation_group_id)},
                    correlation_id=correlation_group_id,
                )
            )
            updated += 1
        self._session.flush()
        self._audit.log(
            tenant_id=tenant_id,
            action=AuditAction.CORRELATED,
            actor=actor,
            message="Correlation group assigned",
            details={
                "correlation_group_id": str(correlation_group_id),
                "finding_ids": [str(item) for item in finding_ids],
                "updated": updated,
            },
        )
        return updated

    def list_correlated(
        self,
        tenant_id: UUID,
        correlation_group_id: UUID,
    ) -> List[SecurityFindingObject]:
        stmt = select(FindingORM).where(
            FindingORM.tenant_id == tenant_id,
            FindingORM.correlation_group_id == correlation_group_id,
        )
        rows = self._session.scalars(stmt).all()
        return [orm_to_finding(row) for row in rows]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_finding(self, finding_id: UUID, tenant_id: UUID) -> FindingORM:
        row = self._session.get(FindingORM, finding_id)
        if row is None or row.tenant_id != tenant_id:
            raise FindingNotFoundError(finding_id, tenant_id)
        return row

    def _add_history(self, entry: FindingHistory) -> None:
        self._session.add(
            FindingHistoryORM(
                id=entry.id,
                finding_id=entry.finding_id,
                tenant_id=entry.tenant_id,
                action=entry.action.value,
                from_status=entry.from_status.value if entry.from_status else None,
                to_status=entry.to_status.value if entry.to_status else None,
                from_lifecycle=entry.from_lifecycle.value if entry.from_lifecycle else None,
                to_lifecycle=entry.to_lifecycle.value if entry.to_lifecycle else None,
                actor=entry.actor,
                message=entry.message,
                details=entry.details,
                correlation_id=entry.correlation_id,
                created_at=entry.created_at,
            )
        )

    def _upsert_evidence_row(
        self,
        *,
        finding_id: UUID,
        tenant_id: UUID,
        evidence: EvidenceObject,
        actor: Optional[str],
        change_summary: str,
    ) -> EvidenceORM:
        row = self._session.get(EvidenceORM, evidence.id)
        if row is not None and row.tenant_id != tenant_id:
            raise TenantIsolationError(
                "Evidence id exists under a different tenant",
                details={"evidence_id": str(evidence.id)},
            )

        if row is None:
            version = 1
            row = evidence_to_orm(
                evidence,
                finding_id=finding_id,
                tenant_id=tenant_id,
                current_version=version,
            )
            self._session.add(row)
            action = AuditAction.EVIDENCE_ATTACHED
        else:
            if row.finding_id != finding_id:
                raise TenantIsolationError(
                    "Evidence belongs to a different finding",
                    details={
                        "evidence_id": str(evidence.id),
                        "finding_id": str(finding_id),
                    },
                )
            version = int(row.current_version) + 1
            apply_evidence_to_orm(row, evidence, current_version=version)
            action = AuditAction.EVIDENCE_VERSIONED

        self._session.add(
            EvidenceVersionORM(
                id=uuid4(),
                evidence_id=evidence.id,
                finding_id=finding_id,
                tenant_id=tenant_id,
                version=version,
                change_summary=change_summary,
                created_by=actor,
                payload=evidence.model_dump(mode="json"),
                created_at=utc_now(),
            )
        )
        self._add_history(
            FindingHistory(
                finding_id=finding_id,
                tenant_id=tenant_id,
                action=action,
                actor=actor,
                message=change_summary,
                details={"evidence_id": str(evidence.id), "version": version},
            )
        )
        return row

    def _build_search_query(self, filters: FindingSearchFilter) -> Select[tuple[FindingORM]]:
        stmt: Select[tuple[FindingORM]] = select(FindingORM).where(
            FindingORM.tenant_id == filters.tenant_id
        )

        if filters.asset_id is not None:
            stmt = stmt.where(FindingORM.asset_id == filters.asset_id)
        if filters.severities:
            stmt = stmt.where(
                FindingORM.severity.in_([item.value for item in filters.severities])
            )
        if filters.scanners:
            stmt = stmt.where(
                FindingORM.source_tool.in_([item.value for item in filters.scanners])
            )
        if filters.statuses:
            stmt = stmt.where(
                FindingORM.status.in_([item.value for item in filters.statuses])
            )
        if filters.lifecycles:
            status_values: list[str] = []
            for lifecycle in filters.lifecycles:
                status_values.extend(s.value for s in statuses_for_lifecycle(lifecycle))
            stmt = stmt.where(FindingORM.status.in_(status_values))
        if filters.finding_types:
            stmt = stmt.where(
                FindingORM.finding_type.in_(
                    [item.value for item in filters.finding_types]
                )
            )
        if filters.correlation_group_id is not None:
            stmt = stmt.where(
                FindingORM.correlation_group_id == filters.correlation_group_id
            )
        if filters.fingerprint:
            stmt = stmt.where(FindingORM.fingerprint == filters.fingerprint)
        if filters.created_after is not None:
            stmt = stmt.where(FindingORM.created_at >= filters.created_after)
        if filters.created_before is not None:
            stmt = stmt.where(FindingORM.created_at <= filters.created_before)
        if filters.text:
            pattern = f"%{filters.text.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(FindingORM.title).like(pattern),
                    func.lower(FindingORM.description).like(pattern),
                )
            )
        if filters.cve_id:
            from sqlalchemy import String, cast

            stmt = stmt.where(
                cast(FindingORM.payload, String).like(f'%"{filters.cve_id}"%')
            )
        if not filters.include_suppressed:
            stmt = stmt.where(FindingORM.status != FindingStatus.SUPPRESSED.value)

        return stmt
