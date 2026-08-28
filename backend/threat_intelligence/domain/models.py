"""Core Threat Intelligence domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from threat_intelligence.domain.enums import (
    CVSSVersion,
    ExploitMaturity,
    ThreatActorSophistication,
    ThreatFeedProviderId,
)


class VulnerabilityReference(FortiBaseModel):
    """External vulnerability / advisory reference."""

    url: str = Field(..., min_length=1, max_length=2048)
    source: str = Field(..., min_length=1, max_length=128)
    title: Optional[str] = Field(default=None, max_length=512)
    external_id: Optional[str] = Field(default=None, max_length=256)


class CVSSMetric(FortiBaseModel):
    """Single CVSS vector / score observation."""

    version: CVSSVersion = Field(...)
    vector: Optional[str] = Field(default=None, max_length=256)
    base_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    temporal_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    environmental_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    severity: Optional[str] = Field(default=None, max_length=32)


class EPSSScore(FortiBaseModel):
    """Exploit Prediction Scoring System observation."""

    score: float = Field(..., ge=0.0, le=1.0, description="EPSS probability.")
    percentile: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    model_version: Optional[str] = Field(default=None, max_length=64)
    scored_at: Optional[datetime] = None

    @field_validator("scored_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("scored_at must be timezone-aware")
        return value


class ExploitInformation(FortiBaseModel):
    """Exploit availability and active exploitation signals."""

    available: bool = Field(default=False)
    maturity: ExploitMaturity = Field(default=ExploitMaturity.UNKNOWN)
    actively_exploited: bool = Field(default=False)
    in_cisa_kev: bool = Field(default=False)
    kev_date_added: Optional[datetime] = None
    kev_due_date: Optional[datetime] = None
    known_ransomware_use: Optional[bool] = None
    public_exploit_urls: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("public_exploit_urls")
    @classmethod
    def limit_urls(cls, value: List[str]) -> List[str]:
        if len(value) > 64:
            raise ValueError("public_exploit_urls limited to 64")
        return value

    @field_validator("kev_date_added", "kev_due_date", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class MITRETechnique(FortiBaseModel):
    """MITRE ATT&CK technique (and optional tactic) reference."""

    technique_id: str = Field(
        ...,
        min_length=2,
        max_length=32,
        description="e.g. T1059 or T1059.001",
    )
    name: Optional[str] = Field(default=None, max_length=256)
    tactic: Optional[str] = Field(default=None, max_length=128)
    url: Optional[str] = Field(default=None, max_length=2048)

    @field_validator("technique_id")
    @classmethod
    def normalize_technique(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.startswith("T"):
            raise ValueError("MITRE technique_id must start with T")
        return normalized


class CVERecord(TimestampedModel):
    """Canonical CVE intelligence record."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: Optional[UUID] = Field(
        default=None,
        description="Null for global/shared CVE catalog rows.",
    )
    cve_id: str = Field(..., min_length=9, max_length=32)
    title: Optional[str] = Field(default=None, max_length=512)
    description: Optional[str] = Field(default=None, max_length=8000)
    published_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    cvss_metrics: List[CVSSMetric] = Field(default_factory=list)
    epss: Optional[EPSSScore] = None
    exploit: ExploitInformation = Field(default_factory=ExploitInformation)
    cwe_ids: List[str] = Field(default_factory=list)
    capec_ids: List[str] = Field(default_factory=list)
    mitre_techniques: List[MITRETechnique] = Field(default_factory=list)
    references: List[VulnerabilityReference] = Field(default_factory=list)
    vendors: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    source_providers: List[ThreatFeedProviderId] = Field(default_factory=list)
    confidence_score: float = Field(default=0.7, ge=0.0, le=1.0)
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_updated_at: datetime = Field(default_factory=utc_now)
    current_version: int = Field(default=1, ge=1)

    @field_validator("cve_id")
    @classmethod
    def normalize_cve(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.startswith("CVE-"):
            raise ValueError(f"invalid CVE id: {value}")
        return normalized

    @field_validator("cwe_ids", "capec_ids")
    @classmethod
    def normalize_ids(cls, value: List[str]) -> List[str]:
        out: List[str] = []
        for item in value:
            cleaned = item.strip().upper()
            if cleaned and cleaned not in out:
                out.append(cleaned)
        return out[:64]

    @field_validator("published_at", "modified_at", "first_seen_at", "last_updated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    def primary_cvss(self) -> Optional[CVSSMetric]:
        """Prefer CVSS v4, then v3.1, then first available."""

        order = [CVSSVersion.V4_0, CVSSVersion.V3_1, CVSSVersion.V3_0, CVSSVersion.V2]
        by_version = {m.version: m for m in self.cvss_metrics}
        for version in order:
            if version in by_version:
                return by_version[version]
        return self.cvss_metrics[0] if self.cvss_metrics else None


class ThreatActor(TimestampedModel):
    """Threat actor / intrusion set profile."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=256)
    aliases: List[str] = Field(default_factory=list)
    description: Optional[str] = Field(default=None, max_length=8000)
    sophistication: ThreatActorSophistication = Field(
        default=ThreatActorSophistication.UNKNOWN
    )
    country: Optional[str] = Field(default=None, max_length=128)
    mitre_group_id: Optional[str] = Field(default=None, max_length=32)
    techniques: List[MITRETechnique] = Field(default_factory=list)
    references: List[VulnerabilityReference] = Field(default_factory=list)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_updated_at: datetime = Field(default_factory=utc_now)
    current_version: int = Field(default=1, ge=1)


class MalwareFamily(TimestampedModel):
    """Malware family association."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=256)
    aliases: List[str] = Field(default_factory=list)
    description: Optional[str] = Field(default=None, max_length=8000)
    techniques: List[MITRETechnique] = Field(default_factory=list)
    references: List[VulnerabilityReference] = Field(default_factory=list)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_updated_at: datetime = Field(default_factory=utc_now)
    current_version: int = Field(default=1, ge=1)


class Campaign(TimestampedModel):
    """Threat campaign linking actors, malware, and TTPs."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=8000)
    threat_actor_ids: List[UUID] = Field(default_factory=list)
    malware_family_ids: List[UUID] = Field(default_factory=list)
    cve_ids: List[str] = Field(default_factory=list)
    techniques: List[MITRETechnique] = Field(default_factory=list)
    references: List[VulnerabilityReference] = Field(default_factory=list)
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_updated_at: datetime = Field(default_factory=utc_now)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    current_version: int = Field(default=1, ge=1)

    @field_validator("cve_ids")
    @classmethod
    def normalize_cves(cls, value: List[str]) -> List[str]:
        return [v.strip().upper() for v in value if v.strip()][:128]


class ThreatFeedMetadata(TimestampedModel):
    """Metadata about a configured / synced threat feed."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: Optional[UUID] = Field(
        default=None,
        description="Null for global shared feeds.",
    )
    provider: ThreatFeedProviderId = Field(...)
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)
    enabled: bool = Field(default=True)
    endpoint_hint: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Future connector endpoint (not called yet).",
    )
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = Field(default=None, max_length=64)
    last_sync_message: Optional[str] = Field(default=None, max_length=2000)
    cursor: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Opaque sync cursor for incremental pulls.",
    )
    config: Dict[str, str] = Field(
        default_factory=dict,
        description="Non-secret connector config keys.",
    )
    current_version: int = Field(default=1, ge=1)

    @field_validator("last_sync_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @field_validator("config")
    @classmethod
    def limit_config(cls, value: Dict[str, str]) -> Dict[str, str]:
        if len(value) > 64:
            raise ValueError("config limited to 64 entries")
        return value


class ThreatIntelligence(TimestampedModel):
    """
    Enrichment envelope optionally attached to a SecurityFindingObject.

    Lives in this service (finding stores only ``asset_id`` / CVE ids today);
    enrichment is joined by ``finding_id`` + ``tenant_id``.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    finding_id: Optional[UUID] = Field(
        default=None,
        description="Optional link to SecurityFindingObject.id.",
    )
    cve_ids: List[str] = Field(default_factory=list)
    cve_records: List[CVERecord] = Field(default_factory=list)
    threat_actors: List[ThreatActor] = Field(default_factory=list)
    malware_families: List[MalwareFamily] = Field(default_factory=list)
    campaigns: List[Campaign] = Field(default_factory=list)
    mitre_techniques: List[MITRETechnique] = Field(default_factory=list)
    cwe_ids: List[str] = Field(default_factory=list)
    capec_ids: List[str] = Field(default_factory=list)
    exploit: ExploitInformation = Field(default_factory=ExploitInformation)
    epss: Optional[EPSSScore] = None
    ioc_ids: List[UUID] = Field(default_factory=list)
    references: List[VulnerabilityReference] = Field(default_factory=list)
    source_providers: List[ThreatFeedProviderId] = Field(default_factory=list)
    summary: Optional[str] = Field(default=None, max_length=4000)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_updated_at: datetime = Field(default_factory=utc_now)
    current_version: int = Field(default=1, ge=1)

    @field_validator("cve_ids", "cwe_ids", "capec_ids")
    @classmethod
    def normalize_id_lists(cls, value: List[str]) -> List[str]:
        out: List[str] = []
        for item in value:
            cleaned = item.strip().upper()
            if cleaned and cleaned not in out:
                out.append(cleaned)
        return out[:128]

    @model_validator(mode="after")
    def sync_timestamps(self) -> ThreatIntelligence:
        if self.last_updated_at < self.first_seen_at:
            object.__setattr__(self, "last_updated_at", self.first_seen_at)
        return self
