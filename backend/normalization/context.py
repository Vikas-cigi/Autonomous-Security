"""
Shared request context and result envelopes for normalization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from models.common import FortiBaseModel
from models.security_finding import SecurityFindingObject


class NormalizationContext(FortiBaseModel):
    """
    Tenant / asset binding required to emit canonical findings.

    Adapters never invent tenancy; callers must supply it.
    """

    tenant_id: UUID = Field(..., description="Owning tenant for emitted findings.")
    asset_id: UUID = Field(
        ...,
        description="Primary asset the scan targets (host, account, repo, image).",
    )
    raw_artifact_id: UUID = Field(
        default_factory=uuid4,
        description="Content-addressed id of the stored raw scan artifact.",
    )
    scan_id: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Optional upstream scan / job identifier.",
    )
    default_asset_labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Labels merged into finding metadata.labels.",
    )

    @field_validator("default_asset_labels")
    @classmethod
    def limit_labels(cls, value: Dict[str, str]) -> Dict[str, str]:
        """Cap label cardinality."""

        if len(value) > 32:
            raise ValueError("default_asset_labels limited to 32 entries")
        return value


class NormalizationIssue(FortiBaseModel):
    """Structured record of a rejected or skipped raw item."""

    index: Optional[int] = Field(
        default=None,
        description="Zero-based index of the failing item when applicable.",
    )
    error: str = Field(..., description="Human-readable error message.")
    raw_excerpt: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Redacted excerpt of the offending raw object (never full dump).",
    )


class NormalizationResult(FortiBaseModel):
    """
    Batch result containing only canonical findings plus rejection diagnostics.

    Downstream systems must use ``findings`` exclusively — never ``issues``.
    """

    tool: str = Field(..., description="Tool key that produced the findings.")
    findings: List[SecurityFindingObject] = Field(default_factory=list)
    issues: List[NormalizationIssue] = Field(default_factory=list)
    duplicates_removed: int = Field(
        default=0,
        ge=0,
        description="Count of findings collapsed by deduplication.",
    )

    @property
    def ok(self) -> bool:
        """True when at least one canonical finding was produced."""

        return len(self.findings) > 0
