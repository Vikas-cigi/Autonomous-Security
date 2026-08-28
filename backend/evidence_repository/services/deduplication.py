"""Deduplication service — merge inbound findings into existing records."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from models.security_finding import SecurityFindingObject
from evidence_repository.domain.enums import AuditAction
from evidence_repository.fingerprint import finding_fingerprint
from evidence_repository.interfaces.repository import EvidenceRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeduplicationResult:
    """Outcome of attempting to persist a finding with deduplication."""

    finding: SecurityFindingObject
    created: bool
    merged_into_id: Optional[UUID]
    fingerprint: str


class DeduplicationService:
    """
    Ensures duplicate scanner emissions collapse into one finding identity.

    When a fingerprint already exists for the tenant, evidence and identifiers
    are merged into the existing finding and a new version is stored.
    """

    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository

    def ingest(
        self,
        finding: SecurityFindingObject,
        *,
        actor: Optional[str] = None,
    ) -> DeduplicationResult:
        """Insert or merge a finding by fingerprint."""

        fingerprint = finding_fingerprint(finding)
        existing = self._repository.find_by_fingerprint(
            finding.tenant_id, fingerprint
        )
        if existing is None:
            saved = self._repository.save_finding(
                finding,
                actor=actor,
                change_summary="Dedup ingest — created",
            )
            logger.info(
                "Dedup created finding=%s fingerprint=%s",
                saved.id,
                fingerprint,
            )
            return DeduplicationResult(
                finding=saved,
                created=True,
                merged_into_id=None,
                fingerprint=fingerprint,
            )

        merged = self._merge(existing, finding)
        saved = self._repository.save_finding(
            merged,
            actor=actor,
            change_summary=f"Dedup ingest — merged from {finding.id}",
        )
        logger.info(
            "Dedup merged source=%s target=%s fingerprint=%s action=%s",
            finding.id,
            saved.id,
            fingerprint,
            AuditAction.DEDUPLICATED.value,
        )
        return DeduplicationResult(
            finding=saved,
            created=False,
            merged_into_id=saved.id,
            fingerprint=fingerprint,
        )

    def ingest_many(
        self,
        findings: List[SecurityFindingObject],
        *,
        actor: Optional[str] = None,
    ) -> List[DeduplicationResult]:
        """Ingest a batch with per-item deduplication."""

        return [self.ingest(item, actor=actor) for item in findings]

    def _merge(
        self,
        primary: SecurityFindingObject,
        incoming: SecurityFindingObject,
    ) -> SecurityFindingObject:
        """Merge evidence and identifiers; keep higher confidence / severity signal."""

        evidence = {item.id: item for item in primary.evidence}
        for item in incoming.evidence:
            evidence.setdefault(item.id, item)

        cves = sorted(set(primary.cve_ids) | set(incoming.cve_ids))
        cwes = sorted(set(primary.cwe_ids) | set(incoming.cwe_ids))
        techniques = sorted(
            set(primary.mitre_attack_techniques) | set(incoming.mitre_attack_techniques)
        )
        confidence = max(primary.confidence_score, incoming.confidence_score)

        # Prefer higher severity if incoming is strictly worse.
        from models.enums import Severity

        rank = {
            Severity.UNKNOWN: 0,
            Severity.INFORMATIONAL: 1,
            Severity.LOW: 2,
            Severity.MEDIUM: 3,
            Severity.HIGH: 4,
            Severity.CRITICAL: 5,
        }
        severity = (
            incoming.severity
            if rank[incoming.severity] > rank[primary.severity]
            else primary.severity
        )
        # Keep CVSS inside the severity band required by SecurityFindingObject.
        bands = {
            Severity.CRITICAL: (9.0, 10.0),
            Severity.HIGH: (7.0, 8.9),
            Severity.MEDIUM: (4.0, 6.9),
            Severity.LOW: (0.1, 3.9),
            Severity.INFORMATIONAL: (0.0, 0.0),
            Severity.UNKNOWN: (0.0, 10.0),
        }
        low, high = bands[severity]
        candidates = [v for v in (primary.cvss_score, incoming.cvss_score) if v is not None]
        if severity is Severity.UNKNOWN:
            cvss = max(candidates) if candidates else None
        elif severity is Severity.INFORMATIONAL:
            cvss = 0.0
        else:
            raw = max(candidates) if candidates else (low + high) / 2.0
            cvss = max(low, min(high, raw))

        return primary.model_copy(
            update={
                "evidence": list(evidence.values()),
                "cve_ids": cves,
                "cwe_ids": cwes,
                "mitre_attack_techniques": techniques,
                "confidence_score": confidence,
                "severity": severity,
                "cvss_score": cvss,
                "description": primary.description
                if len(primary.description) >= len(incoming.description)
                else incoming.description,
            }
        )
