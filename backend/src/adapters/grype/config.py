"""Grype adapter configuration."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from src.adapters.base.adapter_config import AdapterConfig


class GrypeAdapterConfig(AdapterConfig):
    """Configuration for the Anchore Grype vulnerability scanner."""

    tool_name: str = Field(default="grype")
    binary_path: str = Field(default="grype")
    output_format: str = Field(
        default="json",
        description="Grype output format: json | table | cyclonedx | sarif.",
    )
    only_fixed: bool = Field(
        default=False,
        description="When True, only report vulnerabilities with known fixes.",
    )
    fail_on: Optional[str] = Field(
        default=None,
        description="Fail with non-zero exit when severity >= threshold (e.g. 'high').",
    )
    add_cpes_if_none: bool = Field(
        default=True,
        description="Generate CPEs for packages that have none.",
    )
