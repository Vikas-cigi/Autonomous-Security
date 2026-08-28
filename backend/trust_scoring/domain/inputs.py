"""Scoring input DTOs — snapshots consumed by the Trust Scoring Engine.

Callers assemble these from Evidence Repository, Asset Inventory, Threat
Intelligence, scanner metadata, and correlation results. The engine never
calls external APIs or sibling module ORM tables directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, utc_now
from models.enums import EvidenceValidationStatus, SourceTool


class EvidenceItemInput(FortiBaseModel):
    """Single evidence artifact summary for quality assessment."""

    evidence_id: Optional[UUID] = None
    validation_status: EvidenceValidationStatus = Field(
        default=EvidenceValidationStatus.UNVALIDATED
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    has_content_hash: bool = Field(default=False)
    has_lineage: bool = Field(default=False)
    source: Optional[str] = Field(default=None, max_length=128)
    age_days: Optional[float] = Field(default=None, ge=0.0)


class ScannerObservationInput(FortiBaseModel):
    """One scanner's observation of the finding (or a related duplicate)."""

    source_tool: SourceTool = Field(...)
    scanner_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    severity_agrees: bool = Field(default=True)
    title_similarity: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Normalized title/signature similarity vs primary finding.",
    )
    observed_at: Optional[datetime] = None

    @field_validator("observed_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return value


class AssetConfidenceInput(FortiBaseModel):
    """Asset inventory signals used for asset confidence."""

    asset_id: UUID = Field(...)
    inventory_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="How well the asset is known / attributed in inventory.",
    )
    ownership_known: bool = Field(default=False)
    environment_known: bool = Field(default=False)
    criticality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    last_seen_days_ago: Optional[float] = Field(default=None, ge=0.0)


class ThreatIntelConfidenceInput(FortiBaseModel):
    """Threat intelligence enrichment confidence signals."""

    enrichment_present: bool = Field(default=False)
    intel_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    cve_match_count: int = Field(default=0, ge=0)
    in_cisa_kev: bool = Field(default=False)
    actively_exploited: bool = Field(default=False)
    epss_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    mitre_technique_count: int = Field(default=0, ge=0)


class IOCConfidenceInput(FortiBaseModel):
    """IOC correlation confidence signals."""

    matched_ioc_count: int = Field(default=0, ge=0)
    max_ioc_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    active_ioc_count: int = Field(default=0, ge=0)


class HistoricalSignalInput(FortiBaseModel):
    """Historical reliability of similar findings / scanners."""

    prior_true_positive_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Rate of confirmed true positives for similar findings.",
    )
    prior_false_positive_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    sample_size: int = Field(default=0, ge=0)
    scanner_historical_accuracy: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    days_since_last_similar: Optional[float] = Field(default=None, ge=0.0)


class CorrelationSignalInput(FortiBaseModel):
    """Finding correlation / duplicate / consistency signals."""

    correlated_finding_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    severity_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    type_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    asset_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    conflicting_status: bool = Field(default=False)


class FindingBaselineInput(FortiBaseModel):
    """Baseline signals taken directly from the SecurityFindingObject."""

    finding_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    asset_id: UUID = Field(...)
    source_tool: SourceTool = Field(...)
    finding_confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)
    has_cve: bool = Field(default=False)
    has_cwe: bool = Field(default=False)
    has_mitre: bool = Field(default=False)
    finding_age_days: float = Field(default=0.0, ge=0.0)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value


class TrustScoringInput(FortiBaseModel):
    """
    Complete deterministic input bundle for trust scoring.

    Identical inputs always produce identical TrustAssessment outputs.
    """

    finding: FindingBaselineInput = Field(...)
    evidence_items: List[EvidenceItemInput] = Field(default_factory=list)
    scanner_observations: List[ScannerObservationInput] = Field(default_factory=list)
    asset: Optional[AssetConfidenceInput] = None
    threat_intel: Optional[ThreatIntelConfidenceInput] = None
    ioc: Optional[IOCConfidenceInput] = None
    historical: Optional[HistoricalSignalInput] = None
    correlation: Optional[CorrelationSignalInput] = None
    apply_time_decay: bool = Field(default=True)

    @field_validator("evidence_items", "scanner_observations")
    @classmethod
    def limit_lists(cls, value: list) -> list:
        if len(value) > 256:
            raise ValueError("input lists are limited to 256 entries")
        return value
