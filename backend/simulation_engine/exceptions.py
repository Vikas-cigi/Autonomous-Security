"""Simulation Engine exceptions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class SimulationEngineError(Exception):
    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class SimulationNotFoundError(SimulationEngineError):
    def __init__(self, simulation_id: UUID, tenant_id: UUID) -> None:
        super().__init__(
            f"Simulation {simulation_id} not found for tenant {tenant_id}",
            details={
                "simulation_id": str(simulation_id),
                "tenant_id": str(tenant_id),
            },
        )


class InvalidSimulationRequestError(SimulationEngineError):
    """Raised when simulation inputs fail structural or business validation."""
