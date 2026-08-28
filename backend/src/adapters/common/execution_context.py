"""Execution context passed into every adapter run."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.common import ActorReference, utc_now
from models.enums import ActionClass, PolicyScope


class EngagementWindow(BaseModel):
    """Optional time window during which scanning is permitted."""

    model_config = ConfigDict(extra="forbid")

    starts_at: datetime = Field(...)
    ends_at: datetime = Field(...)

    @field_validator("starts_at", "ends_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("engagement window timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_order(self) -> EngagementWindow:
        if self.ends_at <= self.starts_at:
            raise ValueError("engagement ends_at must be after starts_at")
        return self

    def contains(self, moment: Optional[datetime] = None) -> bool:
        """Return True when ``moment`` falls inside the window."""

        point = moment or utc_now()
        return self.starts_at <= point <= self.ends_at


class AdapterExecutionContext(BaseModel):
    """
    Full request context for a single adapter invocation.

    Carries tenancy, actor, scope, targets, and policy attributes required
    before any scanner binary is launched.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    correlation_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(...)
    asset_id: UUID = Field(...)
    user: ActorReference = Field(...)
    roles: List[str] = Field(default_factory=list)
    scope: PolicyScope = Field(default=PolicyScope.TENANT)
    action_class: ActionClass = Field(default=ActionClass.SIMULATE)
    environment: Optional[str] = Field(default=None, max_length=64)
    allowed_targets: List[str] = Field(
        default_factory=list,
        description="Explicitly authorized targets (hosts, paths, accounts).",
    )
    targets: List[str] = Field(
        default_factory=list,
        description="Requested scan targets; must be subset of allowed_targets when set.",
    )
    arguments: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    engagement_window: Optional[EngagementWindow] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("roles", "targets", "allowed_targets", "arguments", "tags")
    @classmethod
    def bound_lists(cls, value: List[str]) -> List[str]:
        if len(value) > 256:
            raise ValueError("list limited to 256 entries")
        return value

    @field_validator("environment")
    @classmethod
    def normalize_env(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().lower() if value else value

    @field_validator("roles")
    @classmethod
    def normalize_roles(cls, value: List[str]) -> List[str]:
        return sorted({item.strip().lower() for item in value if item.strip()})
