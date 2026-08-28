"""
Canonical OutcomeObject — terminal result of a remediation workflow.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, new_id, utc_now
from models.enums import OutcomeStatus, Severity


class OutcomeMetrics(FortiBaseModel):
    """Quantitative summary of remediation outcome."""

    duration_seconds: int = Field(..., ge=0, description="Wall-clock duration.")
    steps_executed: int = Field(..., ge=0, description="Number of steps executed.")
    steps_failed: int = Field(..., ge=0, description="Number of steps that failed.")
    residual_severity: Optional[Severity] = Field(
        default=None,
        description="Severity remaining on the finding after the workflow.",
    )
    risk_delta: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Change in risk score (negative means risk reduced).",
    )

    @model_validator(mode="after")
    def steps_consistency(self) -> OutcomeMetrics:
        """Failed steps cannot exceed executed steps."""

        if self.steps_failed > self.steps_executed:
            raise ValueError("steps_failed cannot exceed steps_executed")
        return self


class OutcomeObject(FortiBaseModel):
    """
    Immutable-leaning terminal outcome for audit, SLAs, and learning loops.

    Produced only after remediation/verification conclude. Downstream analytics
    and AI feedback must consume this model rather than scanner callbacks.
    """

    id: UUID = Field(default_factory=new_id, description="Outcome identifier.")
    tenant_id: UUID = Field(..., description="Owning tenant.")
    finding_id: UUID = Field(..., description="Related finding.")
    remediation_id: UUID = Field(..., description="Related remediation.")
    decision_id: UUID = Field(..., description="Related decision.")
    status: OutcomeStatus = Field(..., description="Terminal outcome status.")
    summary: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Canonical outcome narrative.",
    )
    metrics: OutcomeMetrics = Field(..., description="Quantitative outcome metrics.")
    lessons_learned: List[str] = Field(
        default_factory=list,
        description="Operational lessons for future playbooks.",
    )
    recorded_at: datetime = Field(
        default_factory=utc_now,
        description="UTC time the outcome was recorded.",
    )
    closed_by: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Actor or system that closed the workflow.",
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Small operational metadata.",
    )

    @field_validator("recorded_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware datetimes."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @field_validator("lessons_learned")
    @classmethod
    def validate_lessons(cls, value: List[str]) -> List[str]:
        """Bound lesson list size and content."""

        if len(value) > 50:
            raise ValueError("lessons_learned limited to 50 entries")
        for item in value:
            if not item.strip():
                raise ValueError("lessons_learned entries must be non-empty")
            if len(item) > 2000:
                raise ValueError("lesson entry exceeds 2000 characters")
        return value

    @model_validator(mode="after")
    def status_metric_alignment(self) -> OutcomeObject:
        """Align metrics with terminal status semantics."""

        if self.status == OutcomeStatus.SUCCESS:
            if self.metrics.steps_failed != 0:
                raise ValueError("SUCCESS outcomes require steps_failed == 0")
            if self.metrics.residual_severity in {
                Severity.CRITICAL,
                Severity.HIGH,
            }:
                raise ValueError(
                    "SUCCESS outcomes cannot retain critical/high residual severity"
                )

        if self.status == OutcomeStatus.FAILURE and self.metrics.steps_executed == 0:
            raise ValueError(
                "FAILURE outcomes should record executed steps or use CANCELLED"
            )

        if (
            self.status == OutcomeStatus.PARTIAL_SUCCESS
            and self.metrics.steps_failed == 0
        ):
            raise ValueError("PARTIAL_SUCCESS requires at least one failed step")

        return self
