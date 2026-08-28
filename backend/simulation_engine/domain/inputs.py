"""Simulation input snapshots — assembled by callers from upstream modules."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from models.common import FortiBaseModel, utc_now


class PlanStepSnapshot(FortiBaseModel):
    """Minimal remediation step snapshot for dry-run analysis."""

    step_id: UUID = Field(...)
    sequence: int = Field(..., ge=1)
    action: str = Field(..., min_length=1, max_length=512)
    target: str = Field(..., min_length=1, max_length=512)
    kind: str = Field(default="remediation", max_length=64)
    execution_type: str = Field(default="configuration_change", max_length=64)
    is_destructive: bool = Field(default=False)
    requires_approval: bool = Field(default=False)
    estimated_duration_seconds: int = Field(default=60, ge=1)
    timeout_seconds: int = Field(default=300, ge=1)
    depends_on_sequences: List[int] = Field(default_factory=list)


class RollbackStepSnapshot(FortiBaseModel):
    step_id: UUID = Field(...)
    sequence: int = Field(..., ge=1)
    action: str = Field(..., min_length=1, max_length=512)
    target: str = Field(..., min_length=1, max_length=512)
    is_destructive: bool = Field(default=False)
    estimated_duration_seconds: int = Field(default=60, ge=1)


class RemediationPlanSnapshot(FortiBaseModel):
    """RemediationPlan fields required for simulation (no planner ORM coupling)."""

    plan_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    decision_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    execution_type: str = Field(..., min_length=1, max_length=64)
    priority: str = Field(default="p3", max_length=16)
    summary: str = Field(..., min_length=1, max_length=2000)
    steps: List[PlanStepSnapshot] = Field(..., min_length=1)
    rollback_steps: List[RollbackStepSnapshot] = Field(default_factory=list)
    rollback_automatic: bool = Field(default=False)
    planned_downtime_seconds: int = Field(default=0, ge=0)
    change_window_required: bool = Field(default=False)
    approval_required: bool = Field(default=True)
    estimated_risk_reduction: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AssetSimulationInput(FortiBaseModel):
    asset_id: UUID = Field(...)
    hostname: Optional[str] = Field(default=None, max_length=256)
    environment: Optional[str] = Field(default=None, max_length=64)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)
    internet_facing: bool = Field(default=False)
    customer_facing: bool = Field(default=False)
    dependent_asset_ids: List[UUID] = Field(default_factory=list)
    dependent_services: List[str] = Field(default_factory=list)
    compliance_tags: List[str] = Field(default_factory=list)


class RiskSimulationInput(FortiBaseModel):
    enterprise_risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: Optional[str] = Field(default=None, max_length=32)
    business_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    technical_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    compliance_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    operational_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ThreatIntelSimulationInput(FortiBaseModel):
    in_cisa_kev: bool = Field(default=False)
    actively_exploited: bool = Field(default=False)
    epss_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class PolicySimulationInput(FortiBaseModel):
    policy_version: str = Field(default="1.0.0", min_length=1, max_length=64)
    require_simulation: bool = Field(default=True)
    require_approval: bool = Field(default=True)
    require_change_window: bool = Field(default=False)
    max_downtime_seconds: Optional[int] = Field(default=None, ge=0)
    deny_destructive_in_production: bool = Field(default=False)
    deny_without_rollback: bool = Field(default=True)
    blocked_execution_types: List[str] = Field(default_factory=list)
    related_policy_ids: List[UUID] = Field(default_factory=list)
    attributes: Dict[str, str] = Field(default_factory=dict)


class SimulationRequest(FortiBaseModel):
    """Complete deterministic input for dry-run simulation."""

    plan: RemediationPlanSnapshot = Field(...)
    risk: RiskSimulationInput = Field(...)
    asset: Optional[AssetSimulationInput] = None
    threat_intel: Optional[ThreatIntelSimulationInput] = None
    policy: PolicySimulationInput = Field(default_factory=PolicySimulationInput)
    actor: Optional[str] = Field(default=None, max_length=256)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value
