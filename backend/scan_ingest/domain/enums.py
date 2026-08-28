"""Domain enums for Scan / Ingest."""

from __future__ import annotations

from enum import Enum


class ScanMode(str, Enum):
    """
    How the orchestrator obtains RawResult.

    ``simulate`` — deterministic sample payload (no scanner binary).
    ``live`` — invoke AdapterFactory + real tool binary.
    """

    SIMULATE = "simulate"
    LIVE = "live"


class ScanStatus(str, Enum):
    """Terminal status of a scan/ingest job."""

    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    POLICY_DENIED = "policy_denied"
