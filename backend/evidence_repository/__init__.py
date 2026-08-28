"""
Enterprise Evidence Repository — persistence & query layer for canonical findings.

Does not modify Decision Engine, Context Manager, Prompt Builder, Provider Factory,
Normalization Service, Policy Engine, or Adapter Framework.
"""

from evidence_repository.di.container import EvidenceRepositoryContainer
from evidence_repository.domain.history import FindingHistory
from evidence_repository.domain.versioning import EvidenceVersion, FindingVersion
from evidence_repository.interfaces.repository import EvidenceRepository
from evidence_repository.persistence.postgres_repository import PostgresEvidenceRepository
from evidence_repository.query.filters import FindingSearchFilter
from evidence_repository.query.pagination import Page, PageRequest
from evidence_repository.services.correlation import CorrelationService
from evidence_repository.services.deduplication import DeduplicationService
from evidence_repository.services.search import SearchService

__all__ = [
    "CorrelationService",
    "DeduplicationService",
    "EvidenceRepository",
    "EvidenceRepositoryContainer",
    "EvidenceVersion",
    "FindingHistory",
    "FindingSearchFilter",
    "FindingVersion",
    "Page",
    "PageRequest",
    "PostgresEvidenceRepository",
    "SearchService",
]

__version__ = "1.0.0"
