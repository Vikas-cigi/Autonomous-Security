"""Nuclei adapter configuration."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from src.adapters.base.adapter_config import AdapterConfig


class NucleiAdapterConfig(AdapterConfig):
    """Configuration for the Nuclei scanner adapter."""

    tool_name: str = Field(default="nuclei")
    binary_path: str = Field(default="nuclei")
    templates: List[str] = Field(default_factory=list)
    severity_filter: Optional[str] = Field(
        default=None,
        description="Optional Nuclei -severity filter (e.g. critical,high).",
    )
    rate_limit: Optional[int] = Field(default=None, ge=1)
    json_output: bool = Field(default=True)
