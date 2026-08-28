"""Services package exports."""

from evidence_repository.services.audit import AuditLogger
from evidence_repository.services.correlation import CorrelationGroup, CorrelationService
from evidence_repository.services.deduplication import DeduplicationResult, DeduplicationService
from evidence_repository.services.search import SearchService

__all__ = [
    "AuditLogger",
    "CorrelationGroup",
    "CorrelationService",
    "DeduplicationResult",
    "DeduplicationService",
    "SearchService",
]
