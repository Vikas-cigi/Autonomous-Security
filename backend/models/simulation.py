"""
Canonical SimulationObject — pre-execution blast-radius and dry-run results.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, new_id, utc_now
from models.enums import SimulationStatus


class SimulationImpact(FortiBaseModel):
    """Estimated impact of executing a remediation plan."""

    affected_asset_count: int = Field(
        ...,
        ge=0,
        description="Number of assets expected to be touched.",
    )
    downtime_seconds: int = Field(
        default=0,
        ge=0,
        description="Estimated service disruption in seconds.",
    )
    blast_radius: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Blast radius tier: none | asset | group | environment | tenant.",
    )
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Simulated residual operational risk in [0.0, 1.0].",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="Analyst-facing simulation notes.",
    )

    @field_validator("blast_radius")
    @classmethod
    def validate_blast_radius(cls, value: str) -> str:
        """Restrict blast-radius vocabulary."""

        allowed = {"none", "asset", "group", "environment", "tenant"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"blast_radius must be one of {sorted(allowed)}")
        return normalized


class SimulationObject(FortiBaseModel):
    """
    Dry-run / simulation record required before high-impact remediations.

    Remediations reference this object; they must not invent success from
    scanner output alone.
    """

    id: UUID = Field(default_factory=new_id, description="Simulation identifier.")
    remediation_id: Optional[UUID] = Field(
        default=None,
        description="Owning remediation id when already linked.",
    )
    status: SimulationStatus = Field(
        default=SimulationStatus.NOT_RUN,
        description="Simulation lifecycle status.",
    )
    simulator: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Simulation engine or playbook name.",
    )
    impact: Optional[SimulationImpact] = Field(
        default=None,
        description="Impact estimate produced when simulation completes.",
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="UTC start time.",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="UTC completion time.",
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Explicit assumptions used by the simulator.",
    )
    findings: List[str] = Field(
        default_factory=list,
        description="Simulation findings / warnings (canonical text, not raw logs).",
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Small operational metadata.",
    )

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        """Require timezone-aware datetimes."""

        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @field_validator("assumptions", "findings")
    @classmethod
    def limit_string_lists(cls, value: List[str]) -> List[str]:
        """Bound list sizes and entry lengths."""

        if len(value) > 100:
            raise ValueError("list limited to 100 entries")
        for item in value:
            if not item.strip():
                raise ValueError("list entries must be non-empty")
            if len(item) > 2000:
                raise ValueError("list entry exceeds 2000 characters")
        return value

    @model_validator(mode="after")
    def status_consistency(self) -> SimulationObject:
        """Align timestamps and impact with status."""

        terminal = {
            SimulationStatus.PASSED,
            SimulationStatus.FAILED,
            SimulationStatus.INCONCLUSIVE,
        }
        if self.status in terminal:
            if self.completed_at is None:
                raise ValueError(f"{self.status.value} simulations require completed_at")
            if self.impact is None:
                raise ValueError(f"{self.status.value} simulations require impact")
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")
        if self.status == SimulationStatus.RUNNING and self.started_at is None:
            self.started_at = utc_now()
        return self

    def mark_passed(self, impact: SimulationImpact) -> None:
        """Transition simulation to PASSED with impact (validated assignment)."""

        self.impact = impact
        self.completed_at = utc_now()
        if self.started_at is None:
            self.started_at = self.completed_at
        self.status = SimulationStatus.PASSED
