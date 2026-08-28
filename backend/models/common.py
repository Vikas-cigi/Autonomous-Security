"""
Shared primitives for Forti-ai canonical security models.

Provides identity helpers, timestamp mixins, and reusable constrained types
so domain objects remain consistent across repositories and workflows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def new_id() -> UUID:
    """Allocate a new UUID4 identity."""

    return uuid4()


class FortiBaseModel(BaseModel):
    """
    Base model for all canonical security-domain objects.

    - ``extra='forbid'`` prevents silent acceptance of raw scanner fields.
    - ``str_strip_whitespace`` normalizes accidental padding from adapters.
    - ``validate_assignment`` keeps mutations validated after construction.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
        populate_by_name=True,
    )


class TimestampedModel(FortiBaseModel):
    """Objects that track creation and last-update times in UTC."""

    created_at: datetime = Field(
        default_factory=utc_now,
        description="UTC timestamp when the record was created.",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="UTC timestamp when the record was last modified.",
    )

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: Any) -> Any:
        """Reject naive datetimes; coerce ISO strings via Pydantic normally."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware (UTC recommended)")
        return value

    @model_validator(mode="after")
    def updated_not_before_created(self) -> TimestampedModel:
        """Guarantee updated_at is never earlier than created_at."""

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self

    def touch(self) -> None:
        """Bump ``updated_at`` to the current UTC time."""

        self.updated_at = utc_now()


class TenantScoped(FortiBaseModel):
    """Mixin for tenant isolation — mandatory in multi-tenant enterprise use."""

    tenant_id: UUID = Field(
        ...,
        description="Owning tenant identifier. Required for isolation and ACL.",
    )


class ActorReference(FortiBaseModel):
    """Reference to a human, service account, or automated owner/approver."""

    actor_id: UUID = Field(..., description="Stable identity of the actor.")
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Human-readable actor name for audit trails.",
    )
    email: Optional[str] = Field(
        default=None,
        max_length=320,
        description="Optional contact email for notifications.",
    )
    actor_type: str = Field(
        default="user",
        description="Actor class: user | service | system | ai_agent.",
    )

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: Optional[str]) -> Optional[str]:
        """Lightweight email shape check without external dependencies."""

        if value is None:
            return value
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("email must be a valid address shape")
        return value.lower()

    @field_validator("actor_type")
    @classmethod
    def validate_actor_type(cls, value: str) -> str:
        """Restrict actor_type to the known closed set."""

        allowed = {"user", "service", "system", "ai_agent"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"actor_type must be one of {sorted(allowed)}")
        return normalized


class Score(FortiBaseModel):
    """Normalized score in the closed interval [0.0, 1.0]."""

    value: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score in [0.0, 1.0].",
    )


class MetadataBag(FortiBaseModel):
    """
    Extensible but controlled metadata envelope.

    Raw scanner payloads must be stored as referenced artifacts (via evidence
    lineage), not dumped wholesale into metadata.
    """

    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Short string tags for search and routing.",
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Operational labels (env, region, criticality tier).",
    )
    annotations: Dict[str, Any] = Field(
        default_factory=dict,
        description="Non-authoritative annotations; never replace canonical fields.",
    )

    @field_validator("tags", "labels")
    @classmethod
    def limit_map_size(cls, value: Dict[str, str]) -> Dict[str, str]:
        """Prevent metadata abuse as a raw-dump sink."""

        if len(value) > 64:
            raise ValueError("metadata maps are limited to 64 entries")
        for key, item in value.items():
            if len(key) > 128 or len(item) > 512:
                raise ValueError("metadata key/value lengths exceed limits")
        return value

    @field_validator("annotations")
    @classmethod
    def limit_annotations(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        """Cap annotation cardinality."""

        if len(value) > 32:
            raise ValueError("annotations are limited to 32 entries")
        return value
