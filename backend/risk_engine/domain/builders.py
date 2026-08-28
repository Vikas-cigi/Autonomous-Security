"""Helpers to assemble RiskScoringInput from snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence
from uuid import UUID

from models.common import utc_now
from risk_engine.domain.enums import BusinessContext, ComplianceFramework
from risk_engine.domain.inputs import (
    AssetRiskInput,
    CvssInput,
    EvidenceRiskInput,
    FindingRiskBaselineInput,
    HistoricalRiskInput,
    RiskScoringInput,
    ThreatIntelRiskInput,
    TrustRiskInput,
)


def _age_days(created_at: datetime, *, now: Optional[datetime] = None) -> float:
    ref = now or utc_now()
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    delta = ref - created_at
    return max(0.0, delta.total_seconds() / 86400.0)


def build_risk_scoring_input(
    *,
    finding_id: UUID,
    tenant_id: UUID,
    asset_id: UUID,
    trust_score: float,
    finding_age_days: float = 0.0,
    severity_hint: Optional[float] = None,
    cvss_base_score: Optional[float] = None,
    cvss_version: str = "3.1",
    epss_score: Optional[float] = None,
    in_cisa_kev: bool = False,
    actively_exploited: bool = False,
    mitre_technique_count: int = 0,
    ioc_match_count: int = 0,
    max_ioc_confidence: float = 0.0,
    asset_criticality: float = 0.5,
    business_criticality: float = 0.5,
    environments: Optional[Sequence[BusinessContext]] = None,
    internet_facing: bool = False,
    customer_facing: bool = False,
    compliance_tags: Optional[Sequence[ComplianceFramework]] = None,
    prior_risk_score: Optional[float] = None,
    evidence_count: int = 0,
    validated_evidence_count: int = 0,
    average_evidence_confidence: float = 0.0,
    trust_level: Optional[str] = None,
    recommendation_confidence: Optional[str] = None,
    apply_historical_blend: bool = True,
    evaluated_at: Optional[datetime] = None,
) -> RiskScoringInput:
    """Assemble a RiskScoringInput from primitive snapshots."""

    return RiskScoringInput(
        finding=FindingRiskBaselineInput(
            finding_id=finding_id,
            tenant_id=tenant_id,
            asset_id=asset_id,
            finding_age_days=finding_age_days,
            severity_hint=severity_hint,
            evaluated_at=evaluated_at or utc_now(),
        ),
        trust=TrustRiskInput(
            trust_score=trust_score,
            trust_level=trust_level,
            recommendation_confidence=recommendation_confidence,
        ),
        cvss=(
            CvssInput(version=cvss_version, base_score=cvss_base_score)
            if cvss_base_score is not None
            else None
        ),
        threat_intel=ThreatIntelRiskInput(
            enrichment_present=any(
                [
                    epss_score is not None,
                    in_cisa_kev,
                    actively_exploited,
                    mitre_technique_count > 0,
                    ioc_match_count > 0,
                ]
            ),
            epss_score=epss_score,
            in_cisa_kev=in_cisa_kev,
            actively_exploited=actively_exploited,
            mitre_technique_count=mitre_technique_count,
            ioc_match_count=ioc_match_count,
            max_ioc_confidence=max_ioc_confidence,
        ),
        asset=AssetRiskInput(
            asset_id=asset_id,
            asset_criticality=asset_criticality,
            business_criticality=business_criticality,
            environments=list(environments or []),
            internet_facing=internet_facing,
            customer_facing=customer_facing,
            compliance_tags=list(compliance_tags or []),
        ),
        historical=(
            HistoricalRiskInput(prior_risk_score=prior_risk_score, sample_size=1)
            if prior_risk_score is not None
            else None
        ),
        evidence=EvidenceRiskInput(
            evidence_count=evidence_count,
            validated_evidence_count=validated_evidence_count,
            average_evidence_confidence=average_evidence_confidence,
        ),
        apply_historical_blend=apply_historical_blend,
    )
