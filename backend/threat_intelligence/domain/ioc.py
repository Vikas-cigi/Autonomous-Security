"""IOC domain models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import TimestampedModel, new_id, utc_now
from threat_intelligence.domain.enums import IOCType, ThreatFeedProviderId
from threat_intelligence.domain.models import VulnerabilityReference


class IndicatorOfCompromise(TimestampedModel):
    """Tenant-scoped or global IOC record."""

    id: UUID = Field(default_factory=new_id)
    tenant_id: Optional[UUID] = Field(
        default=None,
        description="Null for globally shared IOCs.",
    )
    ioc_type: IOCType = Field(...)
    value: str = Field(..., min_length=1, max_length=2048)
    normalized_value: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Canonicalized value for correlation.",
    )
    description: Optional[str] = Field(default=None, max_length=4000)
    tags: List[str] = Field(default_factory=list)
    threat_actor_ids: List[UUID] = Field(default_factory=list)
    malware_family_ids: List[UUID] = Field(default_factory=list)
    campaign_ids: List[UUID] = Field(default_factory=list)
    cve_ids: List[str] = Field(default_factory=list)
    references: List[VulnerabilityReference] = Field(default_factory=list)
    source_providers: List[ThreatFeedProviderId] = Field(default_factory=list)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)
    last_updated_at: datetime = Field(default_factory=utc_now)
    is_active: bool = Field(default=True)
    current_version: int = Field(default=1, ge=1)

    @field_validator("value", "normalized_value")
    @classmethod
    def strip_value(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: List[str]) -> List[str]:
        return [t.strip().lower() for t in value if t.strip()][:64]

    @field_validator("cve_ids")
    @classmethod
    def normalize_cves(cls, value: List[str]) -> List[str]:
        return [v.strip().upper() for v in value if v.strip()][:64]

    @field_validator(
        "first_seen_at",
        "last_seen_at",
        "last_updated_at",
        mode="before",
    )
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @classmethod
    def from_raw(
        cls,
        *,
        ioc_type: IOCType,
        value: str,
        tenant_id: Optional[UUID] = None,
        **kwargs,
    ) -> IndicatorOfCompromise:
        """Factory that normalizes common IOC shapes."""

        raw = value.strip()
        if ioc_type in {
            IOCType.DOMAIN,
            IOCType.EMAIL,
            IOCType.URL,
        }:
            normalized = raw.lower()
        elif ioc_type in {
            IOCType.FILE_HASH_MD5,
            IOCType.FILE_HASH_SHA1,
            IOCType.FILE_HASH_SHA256,
            IOCType.CVE,
        }:
            normalized = raw.lower() if ioc_type != IOCType.CVE else raw.upper()
        else:
            normalized = raw
        return cls(
            tenant_id=tenant_id,
            ioc_type=ioc_type,
            value=raw,
            normalized_value=normalized,
            **kwargs,
        )
