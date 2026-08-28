"""Core Enterprise Simulation Engine domain models."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import FortiBaseModel, TimestampedModel, new_id, utc_now
from models.enums import SimulationStatus
from models.simulation import SimulationImpact, SimulationObject
from simulation_engine.domain.enums import (
    BlastRadiusTier,
    SimulationOutcome,
    StepSimulationStatus,
    WarningSeverity,
)

ALGORITHM_VERSION = "1.0.0"
SIMULATOR_NAME = "xolaris.simulation_engine"


class SimulationWarning(FortiBaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    severity: WarningSeverity = Field(...)
    message: str = Field(..., min_length=1, max_length=2000)


class SimulationStep(FortiBaseModel):
    """Dry-run prediction for one remediation step."""

    step_id: UUID = Field(...)
    sequence: int = Field(..., ge=1)
    action: str = Field(..., min_length=1, max_length=512)
    target: str = Field(..., min_length=1, max_length=512)
    status: StepSimulationStatus = Field(...)
    predicted_duration_seconds: int = Field(..., ge=0)
    is_destructive: bool = Field(default=False)
    notes: str = Field(default="", max_length=2000)


class BlastRadius(FortiBaseModel):
    tier: BlastRadiusTier = Field(...)
    affected_asset_ids: List[UUID] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    explanation: str = Field(..., min_length=1, max_length=2000)


class DependencyImpact(FortiBaseModel):
    dependent_asset_count: int = Field(..., ge=0)
    dependent_service_count: int = Field(..., ge=0)
    cascading_risk: float = Field(..., ge=0.0, le=1.0)
    blocked_by_missing_dependency: bool = Field(default=False)
    explanation: str = Field(..., min_length=1, max_length=2000)


class RollbackAssessment(FortiBaseModel):
    rollback_possible: bool = Field(...)
    automatic_rollback: bool = Field(default=False)
    rollback_step_count: int = Field(..., ge=0)
    estimated_rollback_seconds: int = Field(..., ge=0)
    gaps: List[str] = Field(default_factory=list)
    explanation: str = Field(..., min_length=1, max_length=2000)


class PolicyImpact(FortiBaseModel):
    policy_version: str = Field(..., min_length=1, max_length=64)
    violations: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    requires_approval: bool = Field(default=True)
    requires_change_window: bool = Field(default=False)
    explanation: str = Field(..., min_length=1, max_length=2000)

    @property
    def has_blocking_violation(self) -> bool:
        return bool(self.violations)


class DowntimeEstimate(FortiBaseModel):
    seconds: int = Field(..., ge=0)
    maintenance_window_recommended: bool = Field(default=False)
    preferred_window_start: Optional[datetime] = None
    preferred_window_end: Optional[datetime] = None
    explanation: str = Field(..., min_length=1, max_length=2000)

    @field_validator("preferred_window_start", "preferred_window_end", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class RiskReductionEstimate(FortiBaseModel):
    current_risk_score: float = Field(..., ge=0.0, le=100.0)
    predicted_risk_score: float = Field(..., ge=0.0, le=100.0)
    reduction_ratio: float = Field(..., ge=0.0, le=1.0)
    residual_operational_risk: float = Field(..., ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=1, max_length=2000)


class ImpactAssessment(FortiBaseModel):
    blast_radius: BlastRadius = Field(...)
    downtime: DowntimeEstimate = Field(...)
    dependency_impact: DependencyImpact = Field(...)
    rollback: RollbackAssessment = Field(...)
    policy_impact: PolicyImpact = Field(...)
    risk_reduction: RiskReductionEstimate = Field(...)
    compliance_impact_notes: List[str] = Field(default_factory=list)


class SimulationResult(TimestampedModel):
    """
    Dry-run simulation envelope for a RemediationPlan.

    Predicts impact without infrastructure changes or external API execution.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    plan_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    decision_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    outcome: SimulationOutcome = Field(...)
    safe_to_execute: bool = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    summary: str = Field(..., min_length=1, max_length=8000)
    steps: List[SimulationStep] = Field(default_factory=list)
    impact: ImpactAssessment = Field(...)
    warnings: List[SimulationWarning] = Field(default_factory=list)
    affected_assets: List[UUID] = Field(default_factory=list)
    policy_violations: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    algorithm_version: str = Field(default=ALGORITHM_VERSION, min_length=1, max_length=32)
    current_version: int = Field(default=1, ge=1)
    simulated_at: datetime = Field(default_factory=utc_now)
    first_simulated_at: datetime = Field(default_factory=utc_now)
    last_simulated_at: datetime = Field(default_factory=utc_now)

    @field_validator("simulated_at", "first_simulated_at", "last_simulated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def sync_times(self) -> SimulationResult:
        if self.last_simulated_at < self.first_simulated_at:
            object.__setattr__(self, "last_simulated_at", self.first_simulated_at)
        return self

    def to_canonical_simulation_object(
        self,
        *,
        remediation_id: Optional[UUID] = None,
    ) -> SimulationObject:
        """Export to canonical SimulationObject for RemediationObject binding."""

        if self.outcome == SimulationOutcome.SAFE:
            status = SimulationStatus.PASSED
        elif self.outcome == SimulationOutcome.UNSAFE:
            status = SimulationStatus.FAILED
        elif self.outcome == SimulationOutcome.CONDITIONAL:
            status = SimulationStatus.PASSED if self.safe_to_execute else SimulationStatus.INCONCLUSIVE
        else:
            status = SimulationStatus.INCONCLUSIVE

        impact = SimulationImpact(
            affected_asset_count=max(1, len(self.affected_assets)),
            downtime_seconds=self.impact.downtime.seconds,
            blast_radius=self.impact.blast_radius.tier.value,
            risk_score=self.impact.risk_reduction.residual_operational_risk,
            notes=self.summary[:4000],
        )
        findings = [w.message for w in self.warnings][:100]
        findings.extend(self.policy_violations[:20])
        if not findings:
            findings = [self.summary[:2000]]

        obj = SimulationObject(
            id=self.id,
            remediation_id=remediation_id,
            status=SimulationStatus.NOT_RUN,
            simulator=SIMULATOR_NAME,
            impact=None,
            started_at=self.simulated_at,
            completed_at=None,
            assumptions=self.assumptions[:100],
            findings=findings[:100],
            metadata={
                "outcome": self.outcome.value,
                "safe_to_execute": str(self.safe_to_execute).lower(),
                "confidence_score": f"{self.confidence_score:.4f}",
                "algorithm_version": self.algorithm_version,
            },
        )
        # Apply terminal status with required fields via validated assignment path
        if status == SimulationStatus.PASSED:
            obj.impact = impact
            obj.completed_at = self.simulated_at
            obj.status = SimulationStatus.PASSED
        elif status in {SimulationStatus.FAILED, SimulationStatus.INCONCLUSIVE}:
            obj.impact = impact
            obj.completed_at = self.simulated_at
            obj.status = status
        return obj
