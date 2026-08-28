"""Trivy adapter configuration."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from src.adapters.base.adapter_config import AdapterConfig


class TrivyAdapterConfig(AdapterConfig):
    """Configuration for the Trivy scanner adapter."""

    tool_name: str = Field(default="trivy")
    binary_path: str = Field(default="trivy")
    scan_type: str = Field(
        default="image",
        description="Trivy subcommand: image | fs | repo | config | sbom.",
    )
    severity: Optional[str] = Field(default="UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL")
    scanners: List[str] = Field(default_factory=lambda: ["vuln", "secret", "misconfig"])
    format: str = Field(default="json")
