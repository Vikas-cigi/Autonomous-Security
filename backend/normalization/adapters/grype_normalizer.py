"""Grype JSON normalizer."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from models.enums import FindingType, SourceTool
from models.security_finding import SecurityFindingObject
from normalization.base_normalizer import BaseNormalizer
from normalization.context import NormalizationContext
from normalization.exceptions import MalformedInputError, NormalizationItemError
from normalization.mapping import clamp_cvss, map_severity


class GrypeNormalizer(BaseNormalizer):
    """
    Normalize Anchore Grype vulnerability matches.

    Accepts ``{\"matches\": [...]}`` documents or a bare matches list.
    """

    @property
    def tool_key(self) -> str:
        return "grype"

    @property
    def source_tool(self) -> SourceTool:
        return SourceTool.GRYPE

    def extract_items(self, raw_payload: Any) -> Sequence[Dict[str, Any]]:
        if isinstance(raw_payload, list):
            return raw_payload

        if not isinstance(raw_payload, dict):
            raise MalformedInputError(
                "Grype payload must be an object or list",
                tool=self.tool_key,
            )

        matches = raw_payload.get("matches") or raw_payload.get("Matches")
        if isinstance(matches, list):
            return matches

        if "vulnerability" in raw_payload or "artifact" in raw_payload:
            return [raw_payload]

        raise MalformedInputError(
            "Grype payload missing matches array",
            tool=self.tool_key,
        )

    def normalize_item(
        self,
        item: Dict[str, Any],
        context: NormalizationContext,
    ) -> SecurityFindingObject:
        vulnerability = item.get("vulnerability")
        if not isinstance(vulnerability, dict):
            raise NormalizationItemError(
                "Grype match missing vulnerability object",
                tool=self.tool_key,
            )

        vuln_id = vulnerability.get("id") or vulnerability.get("ID")
        if not vuln_id:
            raise NormalizationItemError(
                "Grype vulnerability missing id",
                tool=self.tool_key,
            )

        artifact = item.get("artifact") if isinstance(item.get("artifact"), dict) else {}
        pkg_name = artifact.get("name") or ""
        pkg_version = artifact.get("version") or ""

        severity = map_severity(vulnerability.get("severity") or vulnerability.get("Severity"))
        description = str(
            vulnerability.get("description")
            or vulnerability.get("Description")
            or f"Grype matched {vuln_id} on {pkg_name}@{pkg_version}".strip("@")
        )
        title = f"{vuln_id} in {pkg_name}".strip() if pkg_name else str(vuln_id)

        cves: List[str] = []
        if str(vuln_id).upper().startswith("CVE-"):
            cves = [str(vuln_id).upper()]
        related = vulnerability.get("relatedVulnerabilities") or []
        if isinstance(related, list):
            for rel in related:
                if isinstance(rel, dict):
                    rel_id = str(rel.get("id") or "")
                    if rel_id.upper().startswith("CVE-"):
                        cves.append(rel_id.upper())
        cves = sorted(set(cves))

        cvss_score = None
        cvss_list = vulnerability.get("cvss") or []
        if isinstance(cvss_list, list):
            for entry in cvss_list:
                if isinstance(entry, dict):
                    metrics = entry.get("metrics") or {}
                    if isinstance(metrics, dict) and metrics.get("baseScore") is not None:
                        cvss_score = metrics.get("baseScore")
                        break

        evidence = self.build_evidence(
            context=context,
            summary=f"Grype {vuln_id} package={pkg_name}@{pkg_version}",
            item=item,
            confidence=0.85,
        )

        return SecurityFindingObject(
            tenant_id=context.tenant_id,
            asset_id=context.asset_id,
            source_tool=self.source_tool,
            finding_type=FindingType.VULNERABILITY,
            severity=severity,
            cvss_score=clamp_cvss(cvss_score, severity),
            confidence_score=0.83,
            evidence=[evidence],
            title=title[:512],
            description=description[:20000],
            cve_ids=cves,
            metadata=self.base_metadata(
                context,
                rule_id=str(vuln_id),
                extra_labels={
                    k: str(v)[:512]
                    for k, v in {
                        "package": pkg_name,
                        "version": pkg_version,
                    }.items()
                    if v
                },
            ),
        )
