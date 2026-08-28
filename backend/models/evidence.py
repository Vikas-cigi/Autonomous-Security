"""
Canonical EvidenceObject — attested artifacts supporting a security finding.

Adapters must store scanner blobs as content-addressed artifacts and reference
them here. Downstream systems consume ``EvidenceObject``, never raw scanner JSON.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, utc_now
from models.enums import (
    EvidenceSource,
    EvidenceValidationStatus,
    HashAlgorithm,
    SourceTool,
)


class EvidenceLineage(FortiBaseModel):
    """
    Provenance chain for an evidence artifact.

    Captures how raw input was transformed into canonical evidence so audits
    can reconstruct trust without re-ingesting vendor payloads.
    """

    parent_artifact_ids: List[UUID] = Field(
        default_factory=list,
        description="Upstream artifact IDs this evidence was derived from.",
    )
    transformation: str = Field(
        default="normalize",
        min_length=1,
        max_length=128,
        description="Transformation applied: normalize | redact | enrich | correlate.",
    )
    transformer: str = Field(
        default="forti-ai.adapter",
        min_length=1,
        max_length=256,
        description="Service or component that produced this evidence record.",
    )
    source_tool: Optional[SourceTool] = Field(
        default=None,
        description="Normalized tool that originally emitted the artifact.",
    )
    adapter_version: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Semantic version of the ingest adapter.",
    )

    @field_validator("parent_artifact_ids")
    @classmethod
    def unique_parents(cls, value: List[UUID]) -> List[UUID]:
        """Disallow duplicate parent references."""

        if len(value) != len(set(value)):
            raise ValueError("parent_artifact_ids must be unique")
        if len(value) > 32:
            raise ValueError("lineage depth/fan-in is limited to 32 parents")
        return value


class ContentHash(FortiBaseModel):
    """Content-addressed integrity fingerprint for an artifact."""

    algorithm: HashAlgorithm = Field(
        default=HashAlgorithm.SHA256,
        description="Hash algorithm used to fingerprint the artifact.",
    )
    value: str = Field(
        ...,
        min_length=16,
        max_length=128,
        description="Hex-encoded digest of the artifact bytes.",
    )

    @field_validator("value")
    @classmethod
    def validate_hex_digest(cls, value: str) -> str:
        """Require lowercase hex digests."""

        normalized = value.strip().lower()
        if any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("hash value must be hexadecimal")
        return normalized

    @model_validator(mode="after")
    def validate_digest_length(self) -> ContentHash:
        """Enforce digest length expectations per algorithm."""

        expected = {
            HashAlgorithm.SHA256: 64,
            HashAlgorithm.SHA384: 96,
            HashAlgorithm.SHA512: 128,
            HashAlgorithm.BLAKE3: 64,
        }
        length = expected.get(self.algorithm)
        if length is not None and len(self.value) != length:
            raise ValueError(
                f"{self.algorithm.value} digest must be {length} hex characters"
            )
        return self


class EvidenceObject(FortiBaseModel):
    """
    Canonical evidence record attached to one or more findings.

    The ``raw_artifact_id`` points at immutable storage. The summary and
    validation fields are the only evidence content workflows should trust.
    """

    id: UUID = Field(
        ...,
        description="Canonical evidence identifier.",
    )
    raw_artifact_id: UUID = Field(
        ...,
        description="Immutable reference to stored raw bytes (never inline scanner JSON).",
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Human- and machine-readable summary of what the evidence shows.",
    )
    source: EvidenceSource = Field(
        ...,
        description="Evidence origin class.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence that this evidence accurately supports the finding.",
    )
    hash: ContentHash = Field(
        ...,
        description="Integrity hash of the referenced raw artifact.",
    )
    lineage: EvidenceLineage = Field(
        default_factory=EvidenceLineage,
        description="Derivation / provenance chain for this evidence.",
    )
    validation_status: EvidenceValidationStatus = Field(
        default=EvidenceValidationStatus.UNVALIDATED,
        description="Current validation state of the evidence.",
    )
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="UTC time the evidence was captured or attested.",
    )
    collector: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Optional collector identity (agent id, pipeline name).",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware timestamps."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validated_requires_confidence(self) -> EvidenceObject:
        """Validated evidence must carry meaningful confidence."""

        if (
            self.validation_status == EvidenceValidationStatus.VALIDATED
            and self.confidence < 0.5
        ):
            raise ValueError(
                "validated evidence requires confidence_score >= 0.5"
            )
        if self.validation_status == EvidenceValidationStatus.REJECTED and self.confidence > 0.2:
            raise ValueError(
                "rejected evidence should not claim confidence > 0.2"
            )
        return self
