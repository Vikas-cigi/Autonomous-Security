"""Checkov adapter configuration."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from src.adapters.base.adapter_config import AdapterConfig


class CheckovAdapterConfig(AdapterConfig):
    """Configuration for the Checkov IaC adapter."""

    tool_name: str = Field(default="checkov")
    binary_path: str = Field(default="checkov")
    framework: Optional[str] = Field(
        default=None,
        description="Optional --framework filter (terraform, cloudformation, …).",
    )
    compact: bool = Field(default=True)
    output_format: str = Field(default="json")
    soft_fail: bool = Field(
        default=True,
        description="Use --soft-fail so findings do not force hard process failure.",
    )
    skip_checks: List[str] = Field(default_factory=list)
