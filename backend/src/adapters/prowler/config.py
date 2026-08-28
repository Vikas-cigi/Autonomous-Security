"""Prowler adapter configuration."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from src.adapters.base.adapter_config import AdapterConfig


class ProwlerAdapterConfig(AdapterConfig):
    """Configuration for the Prowler cloud security adapter."""

    tool_name: str = Field(default="prowler")
    binary_path: str = Field(default="prowler")
    provider: str = Field(default="aws", description="Cloud provider: aws|azure|gcp.")
    checks: List[str] = Field(default_factory=list)
    output_format: str = Field(default="json-ocsf")
    region: Optional[str] = Field(default=None)
