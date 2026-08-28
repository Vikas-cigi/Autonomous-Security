"""Scan / Ingest orchestrator exceptions."""

from __future__ import annotations

from typing import Any, Dict, Optional


class ScanIngestError(Exception):
    """Base error for the Scan / Ingest package."""

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.details = details or {}


class ScanValidationError(ScanIngestError):
    """Invalid scan request."""


class ScanAdapterError(ScanIngestError):
    """Adapter execution failed or was denied."""


class ScanTargetParseError(ScanIngestError):
    """Could not extract a scan target from chat/user text."""
