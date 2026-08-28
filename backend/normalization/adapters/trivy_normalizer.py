"""Trivy JSON normalizer."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from models.enums import FindingType, SourceTool
from models.security_finding import SecurityFindingObject
from normalization.base_normalizer import BaseNormalizer
from normalization.context import NormalizationContext
from normalization.exceptions import MalformedInputError, NormalizationItemError
from normalization.mapping import clamp_cvss, map_finding_type, map_severity


class TrivyNormalizer(BaseNormalizer):
    """
    Normalize Trivy vulnerability / misconfiguration / secret reports.

    Accepts Trivy JSON with top-level ``Results`` arrays.
    """

    @property
    def tool_key(self) -> str:
        return "trivy"

    @property
    def source_tool(self) -> SourceTool:
        return SourceTool.TRIVY

    def extract_items(self, raw_payload: Any) -> Sequence[Dict[str, Any]]:
        if isinstance(raw_payload, list):
            if raw_payload and isinstance(raw_payload[0], dict) and (
                "VulnerabilityID" in raw_payload[0] or "MisconfID" in raw_payload[0]
            ):
                return raw_payload
            items: List[Dict[str, Any]] = []
            for entry in raw_payload:
                if isinstance(entry, dict):
                    items.extend(self._flatten_result(entry))
            return items

        if not isinstance(raw_payload, dict):
            raise MalformedInputError(
                "Trivy payload must be an object or list",
                tool=self.tool_key,
            )

        results = raw_payload.get("Results") or raw_payload.get("results")
        if not isinstance(results, list):
            if "VulnerabilityID" in raw_payload:
                return [raw_payload]
            raise MalformedInputError(
                "Trivy payload missing Results array",
                tool=self.tool_key,
            )

        items = []
        for entry in results:
            if isinstance(entry, dict):
                items.extend(self._flatten_result(entry))
        return items

    def _flatten_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        target = result.get("Target") or result.get("target") or ""
        class_name = result.get("Class") or result.get("class") or ""
        result_type = result.get("Type") or result.get("type") or ""
        flattened: List[Dict[str, Any]] = []

        for key, default_kind in (
            ("Vulnerabilities", "vulnerability"),
            ("vulnerabilities", "vulnerability"),
            ("Misconfigurations", "misconfiguration"),
            ("misconfigurations", "misconfiguration"),
            ("Secrets", "secret"),
            ("secrets", "secret"),
        ):
            rows = result.get(key) or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                enriched = dict(row)
                enriched["_trivy_target"] = target
                enriched["_trivy_class"] = class_name
                enriched["_trivy_type"] = result_type
                enriched["_trivy_kind"] = default_kind
                flattened.append(enriched)
        return flattened

    def normalize_item(
        self,
        item: Dict[str, Any],
        context: NormalizationContext,
    ) -> SecurityFindingObject:
        kind = str(item.get("_trivy_kind") or "vulnerability")
        vuln_id = (
            item.get("VulnerabilityID")
            or item.get("MisconfID")
            or item.get("AVDID")
            or item.get("RuleID")
        )
        title = str(item.get("Title") or item.get("title") or vuln_id or "")
        if not vuln_id and not title:
            raise NormalizationItemError(
                "Trivy item missing VulnerabilityID/MisconfID/Title",
                tool=self.tool_key,
            )

        rule_key = str(vuln_id or title)
        severity = map_severity(item.get("Severity") or item.get("severity"))
        description = str(
            item.get("Description")
            or item.get("Message")
            or item.get("description")
            or title
        )
        pkg = item.get("PkgName") or item.get("Package") or ""
        target = item.get("_trivy_target") or ""

        cves: List[str] = []
        if rule_key.upper().startswith("CVE-"):
            cves = [rule_key.upper()]
        cve_field = item.get("CVE")
        if isinstance(cve_field, str) and cve_field.upper().startswith("CVE-"):
            cves = [cve_field.upper()]

        cvss_score = None
        cvss_block = item.get("CVSS")
        if isinstance(cvss_block, dict):
            for vendor_score in cvss_block.values():
                if isinstance(vendor_score, dict) and vendor_score.get("V3Score") is not None:
                    cvss_score = vendor_score.get("V3Score")
                    break

        finding_type = map_finding_type(category=kind, default=FindingType.VULNERABILITY)
        if kind == "secret":
            finding_type = FindingType.SECRET_EXPOSURE

        cwes: List[str] = []
        cwe_ids = item.get("CweIDs")
        if isinstance(cwe_ids, list) and cwe_ids:
            cwes = [str(cwe_ids[0])]

        evidence = self.build_evidence(
            context=context,
            summary=f"Trivy {kind} {rule_key} target={target} pkg={pkg}",
            item=item,
            confidence=0.86,
        )

        return SecurityFindingObject(
            tenant_id=context.tenant_id,
            asset_id=context.asset_id,
            source_tool=self.source_tool,
            finding_type=finding_type,
            severity=severity,
            cvss_score=clamp_cvss(cvss_score, severity),
            confidence_score=0.84,
            evidence=[evidence],
            title=(title or rule_key)[:512],
            description=description[:20000],
            cve_ids=cves,
            cwe_ids=cwes,
            metadata=self.base_metadata(
                context,
                rule_id=rule_key,
                extra_labels={
                    k: str(v)[:512]
                    for k, v in {
                        "target": target,
                        "package": pkg,
                        "kind": kind,
                    }.items()
                    if v
                },
            ),
        )
