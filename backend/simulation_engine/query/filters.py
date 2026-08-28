"""Search filters for Simulation Engine."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.common import FortiBaseModel
from simulation_engine.domain.enums import SimulationOutcome


class SimulationSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    plan_id: Optional[UUID] = None
    finding_id: Optional[UUID] = None
    decision_id: Optional[UUID] = None
    outcomes: Optional[List[SimulationOutcome]] = None
    safe_to_execute: Optional[bool] = None
    algorithm_version: Optional[str] = Field(default=None, max_length=32)


class SimulationAuditSearchFilter(FortiBaseModel):
    tenant_id: UUID = Field(...)
    simulation_id: Optional[UUID] = None
    plan_id: Optional[UUID] = None
    actions: Optional[List[str]] = None
