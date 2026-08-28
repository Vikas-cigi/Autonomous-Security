"""SimulationRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from simulation_engine.domain.history import SimulationVersionRecord
from simulation_engine.domain.models import SimulationResult
from simulation_engine.query.filters import SimulationSearchFilter
from simulation_engine.query.pagination import Page, PageRequest


class SimulationRepository(ABC):
    @abstractmethod
    def save(
        self,
        result: SimulationResult,
        *,
        actor: Optional[str] = None,
        change_summary: str = "Simulation result persisted",
    ) -> SimulationResult:
        ...

    @abstractmethod
    def get(self, simulation_id: UUID, tenant_id: UUID) -> SimulationResult:
        ...

    @abstractmethod
    def find_by_plan(
        self, plan_id: UUID, tenant_id: UUID
    ) -> Optional[SimulationResult]:
        ...

    @abstractmethod
    def search(
        self,
        filters: SimulationSearchFilter,
        page: PageRequest,
    ) -> Page[SimulationResult]:
        ...

    @abstractmethod
    def list_versions(
        self, simulation_id: UUID, tenant_id: UUID
    ) -> List[SimulationVersionRecord]:
        ...
