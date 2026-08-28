"""
Enterprise Verification Engine.

Validates whether approved remediation actions were successfully executed and
whether original security findings have been resolved.

Never executes remediation, recalculates risk/trust, invokes AI, modifies plans,
or performs approval.
"""

from verification_engine.di.container import (
    VerificationEngineContainer,
    VerificationEngineServices,
)
from verification_engine.domain.enums import (
    ClosureRecommendation,
    VerificationStatus,
)
from verification_engine.domain.history import (
    VerificationAuditRecord,
    VerificationHistory,
)
from verification_engine.domain.inputs import VerificationRequest
from verification_engine.domain.models import (
    VerificationReport,
    VerificationResult,
    VerificationSummary,
)
from verification_engine.interfaces.verification_audit_repository import (
    VerificationAuditRepository,
)
from verification_engine.interfaces.verification_evidence_repository import (
    VerificationEvidenceRepository,
)
from verification_engine.interfaces.verification_history_repository import (
    VerificationHistoryRepository,
)
from verification_engine.interfaces.verification_repository import VerificationRepository
from verification_engine.services.verification_engine_service import (
    VerificationEngineService,
)

__all__ = [
    "ClosureRecommendation",
    "VerificationAuditRecord",
    "VerificationAuditRepository",
    "VerificationEngineContainer",
    "VerificationEngineService",
    "VerificationEngineServices",
    "VerificationEvidenceRepository",
    "VerificationHistory",
    "VerificationHistoryRepository",
    "VerificationReport",
    "VerificationRepository",
    "VerificationRequest",
    "VerificationResult",
    "VerificationStatus",
    "VerificationSummary",
]

__version__ = "1.0.0"
