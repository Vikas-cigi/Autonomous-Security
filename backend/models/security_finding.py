"""
Canonical SecurityFindingObject — single source of truth for detected risk.

All scanners, ticketing systems, AI modules, and remediation workflows must
consume and emit this model. Raw vendor findings are adapter input only.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from models.common import MetadataBag, TimestampedModel, new_id
from models.enums import (
    BusinessImpact,
    Exploitability,
    FindingStatus,
    FindingType,
    Severity,
    SourceTool,
)
from models.evidence import EvidenceObject


class SecurityFindingObject(TimestampedModel):
    """
    Enterprise security finding in Forti-ai canonical form.

    Evidence is attached as typed ``EvidenceObject`` instances. Do not embed
    raw scanner documents in ``metadata``.
    """

    id: UUID = Field(
        default_factory=new_id,
        description="Canonical finding identifier.",
    )
    tenant_id: UUID = Field(
        ...,
        description="Tenant that owns this finding.",
    )
    asset_id: UUID = Field(
        ...,
        description="Asset (host, identity, service, repo) the finding applies to.",
    )
    source_tool: SourceTool = Field(
        ...,
        description="Normalized tool that first reported the finding.",
    )
    finding_type: FindingType = Field(
        ...,
        description="Canonical finding taxonomy class.",
    )
    severity: Severity = Field(
        ...,
        description="Normalized severity.",
    )
    cvss_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="CVSS base score in [0.0, 10.0] when applicable.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence that the finding is real and correctly classified.",
    )
    business_impact: BusinessImpact = Field(
        default=BusinessImpact.UNKNOWN,
        description="Business impact classification for prioritization.",
    )
    exploitability: Exploitability = Field(
        default=Exploitability.UNKNOWN,
        description="Exploitability assessment.",
    )
    evidence: List[EvidenceObject] = Field(
        default_factory=list,
        description="Supporting canonical evidence objects (not raw scanner payloads).",
    )
    status: FindingStatus = Field(
        default=FindingStatus.NEW,
        description="Finding lifecycle status.",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Short finding title suitable for consoles and tickets.",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="Canonical narrative description of the risk.",
    )
    cve_ids: List[str] = Field(
        default_factory=list,
        description="Related CVE identifiers when applicable.",
    )
    cwe_ids: List[str] = Field(
        default_factory=list,
        description="Related CWE identifiers when applicable.",
    )
    mitre_attack_techniques: List[str] = Field(
        default_factory=list,
        description="MITRE ATT&CK technique IDs (e.g. T1059).",
    )
    metadata: MetadataBag = Field(
        default_factory=MetadataBag,
        description="Controlled metadata envelope; not a raw scanner dump.",
    )

    @field_validator("cve_ids")
    @classmethod
    def normalize_cves(cls, value: List[str]) -> List[str]:
        """Normalize and validate CVE identifiers."""

        normalized: List[str] = []
        for item in value:
            cve = item.strip().upper()
            if not cve.startswith("CVE-"):
                raise ValueError(f"invalid CVE id: {item}")
            parts = cve.split("-")
            if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
                raise ValueError(f"invalid CVE id: {item}")
            normalized.append(cve)
        if len(normalized) != len(set(normalized)):
            raise ValueError("cve_ids must be unique")
        return normalized

    @field_validator("cwe_ids")
    @classmethod
    def normalize_cwes(cls, value: List[str]) -> List[str]:
        """Normalize CWE identifiers to ``CWE-<num>``."""

        normalized: List[str] = []
        for item in value:
            cwe = item.strip().upper()
            if cwe.startswith("CWE-"):
                num = cwe[4:]
            elif cwe.isdigit():
                num = cwe
                cwe = f"CWE-{num}"
            else:
                raise ValueError(f"invalid CWE id: {item}")
            if not num.isdigit():
                raise ValueError(f"invalid CWE id: {item}")
            normalized.append(cwe)
        if len(normalized) != len(set(normalized)):
            raise ValueError("cwe_ids must be unique")
        return normalized

    @field_validator("mitre_attack_techniques")
    @classmethod
    def normalize_mitre(cls, value: List[str]) -> List[str]:
        """Normalize ATT&CK technique IDs (Txxxx or Txxxx.xxx)."""

        normalized: List[str] = []
        for item in value:
            tech = item.strip().upper()
            if not tech.startswith("T"):
                raise ValueError(f"invalid ATT&CK technique id: {item}")
            body = tech[1:]
            if "." in body:
                major, sub = body.split(".", 1)
                if not major.isdigit() or not sub.isdigit():
                    raise ValueError(f"invalid ATT&CK technique id: {item}")
            elif not body.isdigit():
                raise ValueError(f"invalid ATT&CK technique id: {item}")
            normalized.append(tech)
        if len(normalized) != len(set(normalized)):
            raise ValueError("mitre_attack_techniques must be unique")
        return normalized

    @field_validator("evidence")
    @classmethod
    def unique_evidence_ids(cls, value: List[EvidenceObject]) -> List[EvidenceObject]:
        """Ensure evidence entries are unique by id."""

        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence ids must be unique within a finding")
        if len(value) > 100:
            raise ValueError("a finding may reference at most 100 evidence objects")
        return value

    @model_validator(mode="after")
    def severity_cvss_consistency(self) -> SecurityFindingObject:
        """Keep CVSS and severity qualitatively aligned when both are present."""

        if self.cvss_score is None:
            return self

        expected_min: Dict[Severity, float] = {
            Severity.CRITICAL: 9.0,
            Severity.HIGH: 7.0,
            Severity.MEDIUM: 4.0,
            Severity.LOW: 0.1,
            Severity.INFORMATIONAL: 0.0,
            Severity.UNKNOWN: 0.0,
        }
        expected_max: Dict[Severity, float] = {
            Severity.CRITICAL: 10.0,
            Severity.HIGH: 8.9,
            Severity.MEDIUM: 6.9,
            Severity.LOW: 3.9,
            Severity.INFORMATIONAL: 0.0,
            Severity.UNKNOWN: 10.0,
        }

        low = expected_min[self.severity]
        high = expected_max[self.severity]
        if self.severity not in (Severity.UNKNOWN,) and not (low <= self.cvss_score <= high):
            raise ValueError(
                f"cvss_score {self.cvss_score} is inconsistent with severity "
                f"{self.severity.value} (expected {low}-{high})"
            )
        return self

    @model_validator(mode="after")
    def critical_requires_evidence(self) -> SecurityFindingObject:
        """Critical findings must include at least one evidence object."""

        if self.severity == Severity.CRITICAL and not self.evidence:
            raise ValueError("critical findings require at least one EvidenceObject")
        return self

    def primary_evidence(self) -> Optional[EvidenceObject]:
        """Return the highest-confidence evidence item, if any."""

        if not self.evidence:
            return None
        return max(self.evidence, key=lambda item: item.confidence)
