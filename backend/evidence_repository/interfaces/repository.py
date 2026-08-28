"""EvidenceRepository port (hexagonal interface)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Sequence
from uuid import UUID

from models.enums import FindingStatus
from models.evidence import EvidenceObject
from models.security_finding import SecurityFindingObject
from evidence_repository.domain.enums import LifecycleState
from evidence_repository.domain.history import FindingHistory
from evidence_repository.domain.versioning import EvidenceVersion, FindingVersion
from evidence_repository.query.filters import FindingSearchFilter
from evidence_repository.query.pagination import Page, PageRequest


class EvidenceRepository(ABC):
    """
    Persistence port for canonical findings and evidence.

    All methods that accept ``tenant_id`` enforce multi-tenant isolation.
    """

    # ---- Findings ---------------------------------------------------------

    @abstractmethod
    def save_finding(
        self,
        finding: SecurityFindingObject,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Initial persist",
    ) -> SecurityFindingObject:
        """Insert or update a finding; creates a version + history entry."""

    @abstractmethod
    def get_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> SecurityFindingObject:
        """Fetch a finding by id scoped to tenant."""

    @abstractmethod
    def update_status(
        self,
        finding_id: UUID,
        tenant_id: UUID,
        status: FindingStatus,
        *,
        actor: Optional[str] = None,
        message: str = "Status updated",
    ) -> SecurityFindingObject:
        """Transition finding status and append history."""

    @abstractmethod
    def update_lifecycle(
        self,
        finding_id: UUID,
        tenant_id: UUID,
        lifecycle: LifecycleState,
        *,
        actor: Optional[str] = None,
        message: str = "Lifecycle updated",
    ) -> SecurityFindingObject:
        """Map lifecycle bucket to canonical status and persist."""

    @abstractmethod
    def list_finding_versions(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[FindingVersion]:
        """Return immutable finding versions ordered by version asc."""

    @abstractmethod
    def list_finding_history(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[FindingHistory]:
        """Return append-only history ordered by time asc."""

    # ---- Evidence ---------------------------------------------------------

    @abstractmethod
    def save_evidence(
        self,
        finding_id: UUID,
        tenant_id: UUID,
        evidence: EvidenceObject,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Evidence attached",
    ) -> EvidenceObject:
        """Attach or version evidence under a finding."""

    @abstractmethod
    def get_evidence(
        self,
        evidence_id: UUID,
        tenant_id: UUID,
    ) -> EvidenceObject:
        """Fetch evidence by id scoped to tenant."""

    @abstractmethod
    def list_evidence_for_finding(
        self,
        finding_id: UUID,
        tenant_id: UUID,
    ) -> List[EvidenceObject]:
        """List current evidence objects for a finding."""

    @abstractmethod
    def list_evidence_versions(
        self,
        evidence_id: UUID,
        tenant_id: UUID,
    ) -> List[EvidenceVersion]:
        """Return immutable evidence versions ordered by version asc."""

    # ---- Search / correlation helpers -------------------------------------

    @abstractmethod
    def search_findings(
        self,
        filters: FindingSearchFilter,
        page: PageRequest,
    ) -> Page[SecurityFindingObject]:
        """Paginated filtered search with mandatory tenant scope."""

    @abstractmethod
    def find_by_fingerprint(
        self,
        tenant_id: UUID,
        fingerprint: str,
    ) -> Optional[SecurityFindingObject]:
        """Lookup current finding by dedupe fingerprint."""

    @abstractmethod
    def set_correlation_group(
        self,
        tenant_id: UUID,
        finding_ids: Sequence[UUID],
        correlation_group_id: UUID,
        *,
        actor: Optional[str] = None,
    ) -> int:
        """Assign findings to a correlation group; returns updated count."""

    @abstractmethod
    def list_correlated(
        self,
        tenant_id: UUID,
        correlation_group_id: UUID,
    ) -> List[SecurityFindingObject]:
        """List findings in a correlation group for a tenant."""
