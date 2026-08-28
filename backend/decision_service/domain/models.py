"""Core Enterprise Decision Service domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import ActorReference, FortiBaseModel, TimestampedModel, new_id, utc_now
from models.decision import DecisionObject
from models.enums import DecisionAction, Priority, RecommendedAction
from decision_service.domain.enums import (
    DecisionLifecycleStatus,
    DecisionSource,
    SecurityDecisionType,
)


class DecisionReasoning(FortiBaseModel):
    """Structured reasoning traces used to justify a decision."""

    risk_summary: str = Field(..., min_length=1, max_length=4000)
    trust_summary: str = Field(..., min_length=1, max_length=4000)
    threat_summary: str = Field(default="No threat intelligence summary.", max_length=4000)
    policy_summary: str = Field(default="Policy not yet evaluated.", max_length=4000)
    evidence_summary: str = Field(default="No evidence attached.", max_length=4000)
    key_signals: List[str] = Field(default_factory=list)


class DecisionRecommendation(FortiBaseModel):
    """Normalized recommendation prior to canonical DecisionObject emission."""

    decision_type: SecurityDecisionType = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_action: RecommendedAction = Field(...)
    priority: Priority = Field(...)
    next_step: str = Field(..., min_length=1, max_length=2000)
    business_justification: str = Field(..., min_length=1, max_length=4000)
    technical_justification: str = Field(..., min_length=1, max_length=4000)
    source: DecisionSource = Field(default=DecisionSource.AI)
    raw_ai_text: Optional[str] = Field(default=None, max_length=16000)


class DecisionExplanation(FortiBaseModel):
    """Human-readable explanation envelope for operators / auditors."""

    summary: str = Field(..., min_length=1, max_length=8000)
    ai_explanation: Optional[str] = Field(default=None, max_length=8000)
    business_justification: str = Field(..., min_length=1, max_length=4000)
    technical_justification: str = Field(..., min_length=1, max_length=4000)
    risk_summary: str = Field(..., min_length=1, max_length=4000)
    supporting_evidence: List[str] = Field(default_factory=list)
    recommended_next_step: str = Field(..., min_length=1, max_length=2000)


class DecisionContext(FortiBaseModel):
    """
    Aggregated intelligence package prepared for AI / deterministic advisors.

    Assembled by DecisionContextAssembler — no duplicated scoring logic.
    """

    tenant_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    asset_id: UUID = Field(...)
    finding_title: Optional[str] = None
    finding_severity: Optional[str] = None
    trust_score: float = Field(..., ge=0.0, le=100.0)
    trust_level: Optional[str] = None
    enterprise_risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: Optional[str] = None
    risk_priority: Optional[str] = None
    recommended_sla: Optional[str] = None
    internet_facing: bool = Field(default=False)
    customer_facing: bool = Field(default=False)
    in_cisa_kev: bool = Field(default=False)
    actively_exploited: bool = Field(default=False)
    evidence_count: int = Field(default=0, ge=0)
    evidence_ids: List[UUID] = Field(default_factory=list)
    compliance_tags: List[str] = Field(default_factory=list)
    cve_ids: List[str] = Field(default_factory=list)
    reasoning: DecisionReasoning = Field(...)
    operator_message: str = Field(
        ...,
        min_length=1,
        max_length=16000,
        description="Structured natural-language brief for Context Manager / Prompt Builder.",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIRequestEnvelope(FortiBaseModel):
    """Structured AI request produced before ProviderFactory invocation."""

    id: UUID = Field(default_factory=new_id)
    session_id: Optional[str] = None
    provider_name: Optional[str] = None
    system_prompt: str = Field(default="", max_length=16000)
    user_message: str = Field(..., min_length=1, max_length=16000)
    prompt_metadata: Dict[str, Any] = Field(default_factory=dict)
    context_metadata: Dict[str, Any] = Field(default_factory=dict)


class AIResponseEnvelope(FortiBaseModel):
    """Normalized AI response captured for audit / parsing."""

    id: UUID = Field(default_factory=new_id)
    provider: str = Field(..., min_length=1, max_length=64)
    model: str = Field(default="unknown", max_length=128)
    text: str = Field(..., min_length=0, max_length=32000)
    finish_reason: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: Optional[float] = Field(default=None, ge=0.0)


class DecisionResponse(TimestampedModel):
    """
    Orchestration result envelope joined by finding_id + tenant_id.

    Contains the canonical DecisionObject plus AI/audit artifacts.
    """

    id: UUID = Field(default_factory=new_id)
    tenant_id: UUID = Field(...)
    finding_id: UUID = Field(...)
    asset_id: Optional[UUID] = None
    status: DecisionLifecycleStatus = Field(default=DecisionLifecycleStatus.PROPOSED)
    decision_object: DecisionObject = Field(...)
    recommendation: DecisionRecommendation = Field(...)
    explanation: DecisionExplanation = Field(...)
    context: DecisionContext = Field(...)
    ai_request: Optional[AIRequestEnvelope] = None
    ai_response: Optional[AIResponseEnvelope] = None
    policy_verdict: Optional[str] = Field(default=None, max_length=32)
    policy_reason: Optional[str] = Field(default=None, max_length=2000)
    algorithm_version: str = Field(default="1.0.0", min_length=1, max_length=32)
    current_version: int = Field(default=1, ge=1)
    decided_at: datetime = Field(default_factory=utc_now)
    first_decided_at: datetime = Field(default_factory=utc_now)
    last_decided_at: datetime = Field(default_factory=utc_now)

    @field_validator("decided_at", "first_decided_at", "last_decided_at", mode="before")
    @classmethod
    def ensure_tz(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def sync_timestamps(self) -> DecisionResponse:
        if self.last_decided_at < self.first_decided_at:
            object.__setattr__(self, "last_decided_at", self.first_decided_at)
        return self

    @property
    def decision_action(self) -> DecisionAction:
        return self.decision_object.decision

    @property
    def confidence(self) -> float:
        return self.decision_object.confidence
