"""Search filters for threat intelligence."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from threat_intelligence.domain.enums import IOCType, ThreatFeedProviderId


class ThreatIntelSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    finding_id: Optional[UUID] = None
    cve_ids: Optional[List[str]] = None
    actively_exploited_only: bool = False
    in_cisa_kev_only: bool = False
    min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    providers: Optional[List[ThreatFeedProviderId]] = None
    text: Optional[str] = Field(default=None, max_length=256)


class CVESearchFilter(FortiBaseModel):
    tenant_id: Optional[UUID] = None
    cve_ids: Optional[List[str]] = None
    in_cisa_kev_only: bool = False
    actively_exploited_only: bool = False
    min_epss: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    cwe_ids: Optional[List[str]] = None
    text: Optional[str] = Field(default=None, max_length=256)
    include_global: bool = Field(
        default=True,
        description="Include tenant_id IS NULL catalog rows.",
    )


class IOCSearchFilter(FortiBaseModel):
    tenant_id: Optional[UUID] = None
    ioc_types: Optional[List[IOCType]] = None
    values: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    cve_ids: Optional[List[str]] = None
    active_only: bool = True
    include_global: bool = True
    min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
