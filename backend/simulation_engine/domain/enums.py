"""Domain enums for the Enterprise Simulation Engine."""

from __future__ import annotations

from enum import Enum


class SimulationOutcome(str, Enum):
    """Deterministic dry-run outcome."""

    SAFE = "safe"
    CONDITIONAL = "conditional"
    UNSAFE = "unsafe"
    INCONCLUSIVE = "inconclusive"


class BlastRadiusTier(str, Enum):
    """Estimated blast radius of executing the plan."""

    NONE = "none"
    ASSET = "asset"
    GROUP = "group"
    ENVIRONMENT = "environment"
    TENANT = "tenant"


class WarningSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class StepSimulationStatus(str, Enum):
    """Per-step dry-run status (no real execution)."""

    PREDICTED_SUCCESS = "predicted_success"
    PREDICTED_RISK = "predicted_risk"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class AuditAction(str, Enum):
    SIMULATION_STARTED = "simulation_started"
    SIMULATION_COMPLETED = "simulation_completed"
    SIMULATION_FAILED = "simulation_failed"
    SEARCHED = "searched"
    HISTORY_RECORDED = "history_recorded"
    RESULT_SAVED = "result_saved"
