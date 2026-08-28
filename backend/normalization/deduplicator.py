"""
Deduplication of canonical findings within a normalization batch.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Iterable, List, Tuple

from models.security_finding import SecurityFindingObject

logger = logging.getLogger(__name__)


class FindingDeduplicator:
    """
    Collapses duplicate ``SecurityFindingObject`` instances in a batch.

    Fingerprint is derived from tenant, asset, tool, finding type, title,
    CVE set, and optional rule/template id label — never from raw JSON.
    """

    def deduplicate(
        self,
        findings: Iterable[SecurityFindingObject],
    ) -> Tuple[List[SecurityFindingObject], int]:
        """
        Return unique findings and the count of removed duplicates.

        When duplicates collide, the higher-confidence finding is kept and
        evidence lists are merged (unique by evidence id).
        """

        winners: dict[str, SecurityFindingObject] = {}
        removed = 0

        for finding in findings:
            key = self.fingerprint(finding)
            existing = winners.get(key)
            if existing is None:
                winners[key] = finding
                continue

            removed += 1
            logger.info(
                "Deduplicating finding fingerprint=%s kept_id=%s dropped_id=%s",
                key,
                existing.id,
                finding.id,
            )
            winners[key] = self._merge(existing, finding)

        return list(winners.values()), removed

    def fingerprint(self, finding: SecurityFindingObject) -> str:
        """Build a stable fingerprint for a canonical finding."""

        template = finding.metadata.labels.get("rule_id") or finding.metadata.labels.get(
            "template_id", ""
        )
        cves = ",".join(sorted(finding.cve_ids))
        material = "|".join(
            [
                str(finding.tenant_id),
                str(finding.asset_id),
                finding.source_tool.value,
                finding.finding_type.value,
                finding.title.strip().lower(),
                cves,
                template.strip().lower(),
            ]
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _merge(
        self,
        left: SecurityFindingObject,
        right: SecurityFindingObject,
    ) -> SecurityFindingObject:
        """Keep the higher-confidence finding and union evidence."""

        primary, secondary = (
            (left, right)
            if left.confidence_score >= right.confidence_score
            else (right, left)
        )
        evidence_by_id = {item.id: item for item in primary.evidence}
        for item in secondary.evidence:
            evidence_by_id.setdefault(item.id, item)

        cves = sorted(set(primary.cve_ids) | set(secondary.cve_ids))
        cwes = sorted(set(primary.cwe_ids) | set(secondary.cwe_ids))
        techniques = sorted(
            set(primary.mitre_attack_techniques) | set(secondary.mitre_attack_techniques)
        )

        return primary.model_copy(
            update={
                "evidence": list(evidence_by_id.values()),
                "cve_ids": cves,
                "cwe_ids": cwes,
                "mitre_attack_techniques": techniques,
                "confidence_score": max(
                    primary.confidence_score, secondary.confidence_score
                ),
            }
        )
