"""SimulationAuditRepository port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from simulation_engine.domain.history import SimulationAuditRecord
from simulation_engine.query.filters import SimulationAuditSearchFilter
from simulation_engine.query.pagination import Page, PageRequest


class SimulationAuditRepository(ABC):
    @abstractmethod
    def append(self, record: SimulationAuditRecord) -> SimulationAuditRecord:
        ...

    @abstractmethod
    def list_for_simulation(
        self, simulation_id: UUID, tenant_id: UUID
    ) -> List[SimulationAuditRecord]:
        ...

    @abstractmethod
    def search(
        self,
        filters: SimulationAuditSearchFilter,
        page: PageRequest,
    ) -> Page[SimulationAuditRecord]:
        ...
