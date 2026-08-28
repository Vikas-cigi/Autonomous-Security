"""Request / response models for Scan / Ingest."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from models.common import ActorReference, FortiBaseModel, utc_now
from scan_ingest.domain.enums import ScanMode, ScanStatus


class ScanRequest(FortiBaseModel):
    """Inbound scan / ingest request."""

    tenant_id: UUID = Field(...)
    target: str = Field(..., min_length=1, max_length=2048)
    tool_name: str = Field(default="nuclei", min_length=1, max_length=64)
    mode: ScanMode = Field(default=ScanMode.SIMULATE)
    asset_id: Optional[UUID] = Field(
        default=None,
        description="Existing asset; when omitted a target-bound asset is upserted.",
    )
    asset_name: Optional[str] = Field(default=None, max_length=256)
    actor: ActorReference = Field(...)
    roles: List[str] = Field(default_factory=lambda: ["secops"])
    run_pipeline: bool = Field(
        default=True,
        description="When True, run Trust → Risk → Decision → Planner for new findings.",
    )
    invoke_ai_decision: bool = Field(
        default=False,
        description="Pass through to DecisionService (False = deterministic advisor).",
    )
    tags: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    scan_id: Optional[str] = Field(default=None, max_length=256)

    @field_validator("tool_name")
    @classmethod
    def normalize_tool(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("target")
    @classmethod
    def strip_target(cls, value: str) -> str:
        return value.strip()


class IngestedFindingSummary(FortiBaseModel):
    """Compact finding record after evidence ingest."""

    finding_id: UUID = Field(...)
    title: str = Field(...)
    severity: str = Field(...)
    created: bool = Field(...)
    fingerprint: str = Field(...)
    merged_into_id: Optional[UUID] = None


class PipelineFindingResult(FortiBaseModel):
    """Per-finding Trust → Risk → Decision → Plan outcome."""

    finding_id: UUID = Field(...)
    trust_score: Optional[float] = None
    trust_level: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    decision_id: Optional[UUID] = None
    decision_action: Optional[str] = None
    recommended_action: Optional[str] = None
    plan_id: Optional[UUID] = None
    plan_summary: Optional[str] = None
    skipped_reason: Optional[str] = None
    error: Optional[str] = None


class ScanResult(FortiBaseModel):
    """Full scan / ingest / optional pipeline result."""

    scan_id: str = Field(...)
    status: ScanStatus = Field(...)
    mode: ScanMode = Field(...)
    tool_name: str = Field(...)
    tenant_id: UUID = Field(...)
    asset_id: UUID = Field(...)
    target: str = Field(...)
    adapter_status: Optional[str] = None
    raw_artifact_id: UUID = Field(default_factory=uuid4)
    findings_normalized: int = Field(default=0, ge=0)
    findings_created: int = Field(default=0, ge=0)
    findings_merged: int = Field(default=0, ge=0)
    normalization_issues: int = Field(default=0, ge=0)
    findings: List[IngestedFindingSummary] = Field(default_factory=list)
    pipeline: List[PipelineFindingResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    execution_time_ms: float = Field(default=0.0, ge=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_chat_summary(self) -> Dict[str, Any]:
        """Compact dict for ToolResult / chat replies."""

        return {
            "scan_id": self.scan_id,
            "status": self.status.value,
            "mode": self.mode.value,
            "tool": self.tool_name,
            "target": self.target,
            "asset_id": str(self.asset_id),
            "findings_normalized": self.findings_normalized,
            "findings_created": self.findings_created,
            "findings_merged": self.findings_merged,
            "findings": [
                {
                    "id": str(f.finding_id),
                    "title": f.title,
                    "severity": f.severity,
                    "created": f.created,
                }
                for f in self.findings[:10]
            ],
            "pipeline": [
                {
                    "finding_id": str(p.finding_id),
                    "trust": p.trust_score,
                    "risk": p.risk_score,
                    "decision": p.decision_action,
                    "plan_id": str(p.plan_id) if p.plan_id else None,
                    "error": p.error,
                }
                for p in self.pipeline[:10]
            ],
            "errors": self.errors[:5],
        }
