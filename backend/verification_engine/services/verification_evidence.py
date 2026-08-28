"""Normalize and persist verification evidence snapshots."""

from __future__ import annotations

from typing import List, Optional

from models.common import utc_now
from verification_engine.domain.inputs import EvidenceItemInput, VerificationRequest
from verification_engine.domain.models import VerificationEvidence
from verification_engine.interfaces.verification_evidence_repository import (
    VerificationEvidenceRepository,
)


class VerificationEvidenceService:
    """Assemble pre/post/rescan evidence without mutating upstream repositories."""

    def __init__(
        self,
        evidence_repository: Optional[VerificationEvidenceRepository] = None,
    ) -> None:
        self._repo = evidence_repository

    def collect(self, request: VerificationRequest) -> List[VerificationEvidence]:
        items: List[VerificationEvidence] = []
        for e in request.pre_evidence:
            items.append(self._map(e, phase="pre"))
        for e in request.post_evidence:
            items.append(self._map(e, phase="post"))
        if request.rescan.performed and request.rescan.summary:
            items.append(
                VerificationEvidence(
                    phase="rescan",
                    kind="rescan",
                    summary=request.rescan.summary,
                    source=request.rescan.scanner,
                    indicates_resolved=(
                        False
                        if request.rescan.finding_still_present
                        else True
                        if request.rescan.finding_still_present is False
                        else None
                    ),
                    attributes={
                        "performed": "true",
                        "finding_still_present": str(
                            request.rescan.finding_still_present
                        ),
                    },
                    collected_at=request.evaluated_at or utc_now(),
                )
            )
        return items

    def persist(
        self,
        *,
        verification_id,
        tenant_id,
        evidence: List[VerificationEvidence],
    ) -> List[VerificationEvidence]:
        if self._repo is None:
            return evidence
        return self._repo.save_many(verification_id, tenant_id, evidence)

    @staticmethod
    def _map(item: EvidenceItemInput, *, phase: str) -> VerificationEvidence:
        return VerificationEvidence(
            evidence_id=item.evidence_id,
            phase=phase,
            kind=item.kind,
            summary=item.summary,
            source=item.source,
            indicates_resolved=item.indicates_resolved,
            attributes=dict(item.attributes),
            collected_at=item.collected_at or utc_now(),
        )
