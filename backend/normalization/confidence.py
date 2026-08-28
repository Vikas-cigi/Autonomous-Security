"""
Confidence scoring for normalized findings.
"""

from __future__ import annotations

from models.enums import EvidenceValidationStatus, Severity
from models.security_finding import SecurityFindingObject


class ConfidenceScorer:
    """
    Derives a canonical confidence score in ``[0.0, 1.0]``.

    Combines tool prior, evidence quality, severity signal, and identifier richness.
    """

    TOOL_PRIORS = {
        "nuclei": 0.82,
        "prowler": 0.78,
        "checkov": 0.80,
        "trivy": 0.84,
        "grype": 0.83,
    }

    def score(
        self,
        finding: SecurityFindingObject,
        *,
        tool: str,
        has_cve: bool = False,
        has_template_id: bool = False,
    ) -> float:
        """
        Compute confidence for a finding.

        Args:
            finding: Partially built finding (evidence may already be attached).
            tool: Normalizer tool key.
            has_cve: Whether upstream provided a CVE.
            has_template_id: Whether upstream provided a stable rule/template id.
        """

        base = self.TOOL_PRIORS.get(tool.lower(), 0.70)

        if finding.evidence:
            validated = sum(
                1
                for item in finding.evidence
                if item.validation_status
                in {
                    EvidenceValidationStatus.VALIDATED,
                    EvidenceValidationStatus.PARTIALLY_VALIDATED,
                }
            )
            evidence_boost = min(0.12, 0.04 * len(finding.evidence) + 0.06 * validated)
        else:
            evidence_boost = -0.15

        severity_boost = {
            Severity.CRITICAL: 0.05,
            Severity.HIGH: 0.03,
            Severity.MEDIUM: 0.0,
            Severity.LOW: -0.02,
            Severity.INFORMATIONAL: -0.05,
            Severity.UNKNOWN: -0.08,
        }[finding.severity]

        id_boost = 0.0
        if has_cve:
            id_boost += 0.06
        if has_template_id:
            id_boost += 0.04
        if finding.cwe_ids:
            id_boost += 0.02

        score = base + evidence_boost + severity_boost + id_boost
        return round(max(0.05, min(0.99, score)), 4)
