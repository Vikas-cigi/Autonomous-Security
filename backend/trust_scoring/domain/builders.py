"""Helpers to assemble TrustScoringInput from canonical objects + snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence
from uuid import UUID

from models.common import utc_now
from models.enums import EvidenceValidationStatus, SourceTool
from models.evidence import EvidenceObject
from models.security_finding import SecurityFindingObject
from trust_scoring.domain.inputs import (
    AssetConfidenceInput,
    CorrelationSignalInput,
    EvidenceItemInput,
    FindingBaselineInput,
    HistoricalSignalInput,
    IOCConfidenceInput,
    ScannerObservationInput,
    ThreatIntelConfidenceInput,
    TrustScoringInput,
)


def _age_days(created_at: datetime, *, now: Optional[datetime] = None) -> float:
    ref = now or utc_now()
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    delta = ref - created_at
    return max(0.0, delta.total_seconds() / 86400.0)


def evidence_items_from_objects(
    evidence: Sequence[EvidenceObject],
    *,
    now: Optional[datetime] = None,
) -> List[EvidenceItemInput]:
    """Map canonical EvidenceObject list to scoring evidence inputs."""

    items: List[EvidenceItemInput] = []
    for ev in evidence:
        items.append(
            EvidenceItemInput(
                evidence_id=ev.id,
                validation_status=ev.validation_status,
                confidence=ev.confidence,
                has_content_hash=bool(ev.hash and ev.hash.value),
                has_lineage=bool(
                    ev.lineage
                    and (
                        ev.lineage.parent_artifact_ids
                        or ev.lineage.source_tool is not None
                    )
                ),
                source=ev.source.value if ev.source else None,
                age_days=_age_days(ev.timestamp, now=now) if ev.timestamp else None,
            )
        )
    return items


def finding_baseline_from_object(
    finding: SecurityFindingObject,
    *,
    now: Optional[datetime] = None,
) -> FindingBaselineInput:
    """Map SecurityFindingObject to FindingBaselineInput."""

    ref = now or utc_now()
    return FindingBaselineInput(
        finding_id=finding.id,
        tenant_id=finding.tenant_id,
        asset_id=finding.asset_id,
        source_tool=finding.source_tool,
        finding_confidence=finding.confidence_score,
        evidence_count=len(finding.evidence),
        has_cve=bool(finding.cve_ids),
        has_cwe=bool(finding.cwe_ids),
        has_mitre=bool(finding.mitre_attack_techniques),
        finding_age_days=_age_days(finding.created_at, now=ref),
        evaluated_at=ref,
    )


def build_scoring_input(
    finding: SecurityFindingObject,
    *,
    scanner_observations: Optional[List[ScannerObservationInput]] = None,
    asset: Optional[AssetConfidenceInput] = None,
    threat_intel: Optional[ThreatIntelConfidenceInput] = None,
    ioc: Optional[IOCConfidenceInput] = None,
    historical: Optional[HistoricalSignalInput] = None,
    correlation: Optional[CorrelationSignalInput] = None,
    apply_time_decay: bool = True,
    now: Optional[datetime] = None,
) -> TrustScoringInput:
    """
    Assemble a complete TrustScoringInput from a finding and optional snapshots.

    Does not call sibling services — callers supply asset/TI/history/correlation.
    """

    ref = now or utc_now()
    observations = scanner_observations or [
        ScannerObservationInput(
            source_tool=finding.source_tool,
            scanner_confidence=finding.confidence_score,
            severity_agrees=True,
            title_similarity=1.0,
            observed_at=finding.created_at,
        )
    ]
    return TrustScoringInput(
        finding=finding_baseline_from_object(finding, now=ref),
        evidence_items=evidence_items_from_objects(finding.evidence, now=ref),
        scanner_observations=observations,
        asset=asset,
        threat_intel=threat_intel,
        ioc=ioc,
        historical=historical,
        correlation=correlation,
        apply_time_decay=apply_time_decay,
    )


def empty_asset_confidence(asset_id: UUID) -> AssetConfidenceInput:
    """Minimal asset confidence placeholder when inventory data is unavailable."""

    return AssetConfidenceInput(asset_id=asset_id)


def primary_scanner_observation(
    source_tool: SourceTool,
    confidence: float,
    *,
    observed_at: Optional[datetime] = None,
) -> ScannerObservationInput:
    return ScannerObservationInput(
        source_tool=source_tool,
        scanner_confidence=confidence,
        severity_agrees=True,
        title_similarity=1.0,
        observed_at=observed_at,
    )


# Re-export validation status for callers building EvidenceItemInput manually
__all__ = [
    "EvidenceValidationStatus",
    "build_scoring_input",
    "empty_asset_confidence",
    "evidence_items_from_objects",
    "finding_baseline_from_object",
    "primary_scanner_observation",
]
