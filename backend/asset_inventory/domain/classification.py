"""Asset classification and criticality / exposure envelopes."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field, field_validator

from models.common import FortiBaseModel
from asset_inventory.domain.enums import (
    CriticalityTier,
    DataSensitivity,
    ExposureLevel,
)


class InternetExposure(FortiBaseModel):
    """Internet / network exposure posture for an asset."""

    level: ExposureLevel = Field(
        default=ExposureLevel.UNKNOWN,
        description="Exposure classification.",
    )
    public_ips: List[str] = Field(
        default_factory=list,
        description="Known public IP addresses.",
    )
    public_hostnames: List[str] = Field(
        default_factory=list,
        description="Public DNS names.",
    )
    open_ports: List[int] = Field(
        default_factory=list,
        description="Externally reachable ports when known.",
    )
    behind_waf: Optional[bool] = Field(
        default=None,
        description="True when protected by a WAF / edge gateway.",
    )
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("open_ports")
    @classmethod
    def validate_ports(cls, value: List[int]) -> List[int]:
        for port in value:
            if port < 1 or port > 65535:
                raise ValueError("open_ports must be in 1..65535")
        if len(value) > 256:
            raise ValueError("open_ports limited to 256 entries")
        return value

    @field_validator("public_ips", "public_hostnames")
    @classmethod
    def limit_lists(cls, value: List[str]) -> List[str]:
        if len(value) > 64:
            raise ValueError("exposure lists limited to 64 entries")
        return value


class AssetClassification(FortiBaseModel):
    """
    Security / business classification used for prioritization.

    Feeds criticality scoring; does not replace ownership or environment.
    """

    criticality_tier: CriticalityTier = Field(
        default=CriticalityTier.MEDIUM,
        description="Authoritative or last-computed criticality tier.",
    )
    data_sensitivity: DataSensitivity = Field(
        default=DataSensitivity.UNKNOWN,
    )
    business_criticality: CriticalityTier = Field(
        default=CriticalityTier.MEDIUM,
        description="Business-declared criticality (input to scoring).",
    )
    internet_exposure: InternetExposure = Field(
        default_factory=InternetExposure,
    )
    compliance_tags: List[str] = Field(
        default_factory=list,
        description="Compliance frameworks (e.g. pci-dss, hipaa, sox).",
    )
    regulated: bool = Field(
        default=False,
        description="True when asset is in a regulated scope.",
    )
    crown_jewel: bool = Field(
        default=False,
        description="True for crown-jewel / tier-0 assets.",
    )

    @field_validator("compliance_tags")
    @classmethod
    def normalize_compliance_tags(cls, value: List[str]) -> List[str]:
        if len(value) > 32:
            raise ValueError("compliance_tags limited to 32 entries")
        normalized: List[str] = []
        seen = set()
        for tag in value:
            item = tag.strip().lower()
            if not item:
                continue
            if len(item) > 64:
                raise ValueError("compliance tag max length is 64")
            if item not in seen:
                seen.add(item)
                normalized.append(item)
        return normalized
